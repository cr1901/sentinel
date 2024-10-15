/*! Example Rust application for AttoSoC Sentinel SoC.

[Rule 110](https://en.wikipedia.org/wiki/Rule_110) demo using the UART as an
output medium.

*/

#![no_std]
#![no_main]

use atoi::FromRadix10;
use bitvec::prelude::*;
use core::cell::Cell;
use core::mem::MaybeUninit;
use core::ptr::{addr_of_mut, read_volatile, write_volatile};
use core::str;
use critical_section::{self, CriticalSection, Mutex};
use heapless::spsc::{Consumer, Producer, Queue};
use panic_halt as _;
use portable_atomic::{AtomicBool, AtomicU8, Ordering::SeqCst};
use riscv::register::{mie, mstatus};
use riscv_rt::entry;

// Compile-time options
const BUFSIZ: usize = 80;
const INIT_POS: usize = BUFSIZ - 1; // BUFSIZ / 2 or 0 are also good!

static RX: Mutex<Cell<Option<u8>>> = Mutex::new(Cell::new(None));
static TX_IN_PROGRESS: AtomicBool = AtomicBool::new(false);
static COUNT: AtomicU8 = AtomicU8::new(0);
// SAFETY: Emulating a "Send". We never touch this from non interrupt thread
// once this is set.
static mut TX_CONS: MaybeUninit<Consumer<'static, u8, 64>> = MaybeUninit::uninit();

// It is difficult to get CSR and Wishbone periphs to share the same addresses,
// so I don't bother. Instead, use base u32s to access hardware, so that the
// same firmware can be used regardless of board.
pub mod io_addrs {
    /*! I/O address accessor helpers. */
    use riscv::register::mip;

    /** Newtype for `u32` representation of base address of AttoSoC GPIO
    port. */
    #[derive(Clone, Copy)]
    pub struct GpioBase(u32);

    impl From<GpioBase> for u32 {
        fn from(value: GpioBase) -> Self {
            value.0
        }
    }

    /** Newtype for `u32` representation of base address of AttoSoC timer. */
    #[derive(Clone, Copy)]
    pub struct TimerBase(u32);

    impl From<TimerBase> for u32 {
        fn from(value: TimerBase) -> Self {
            value.0
        }
    }

    /** Newtype for `u32` representation of base address of AttoSoC UART. */
    #[derive(Clone, Copy)]
    pub struct SerialBase(u32);

    impl From<SerialBase> for u32 {
        fn from(value: SerialBase) -> Self {
            value.0
        }
    }

    /** Get I/O base addresses via a runtime check of pending UART interrupts.
     
    # Safety
    
    Must be called when interrupts are disabled, as one of the first things
    in the program.
    */
    #[allow(clippy::must_use_candidate)]
    pub unsafe fn get_bases() -> (GpioBase, TimerBase, SerialBase) {
        // If IRQ is pending after reset, we are using WBSerial, and thus a
        // wishbone peripheral bus.
        if mip::read().mext() {
            (
                GpioBase(0x0200_0000),
                TimerBase(0x4000_0000),
                SerialBase(0x8000_0000),
            )
        } else {
            (
                GpioBase(0x0200_0000),
                TimerBase(0x0280_0000),
                SerialBase(0x0300_0000),
            )
        }
    }
}

pub use io_addrs::{GpioBase, SerialBase, TimerBase};

static mut GPIO_BASE: MaybeUninit<GpioBase> = MaybeUninit::uninit();
static mut TIMER_BASE: MaybeUninit<TimerBase> = MaybeUninit::uninit();
static mut SERIAL_BASE: MaybeUninit<SerialBase> = MaybeUninit::uninit();

// `read/write_volatile` SAFETYs: We have a CriticalSection, which means we've
// proven that we have exclusive access or have opted into unsafety previously.
// These are all valid I/O port addresses.
fn read_timer_int(_cs: CriticalSection, base: TimerBase) -> u8 {
    unsafe { read_volatile(u32::from(base) as *const u8) }
}

fn read_serial_int(_cs: CriticalSection, base: SerialBase) -> u8 {
    unsafe { read_volatile((u32::from(base) + 4) as *const u8) }
}

fn read_serial_rx(_cs: CriticalSection, base: SerialBase) -> u8 {
    unsafe { read_volatile(u32::from(base) as *const u8) }
}

fn write_serial_tx(_cs: CriticalSection, base: SerialBase, val: u8) {
    unsafe { write_volatile(u32::from(base) as *mut u8, val) }
}

fn read_inp_port(_cs: CriticalSection, base: GpioBase) -> u8 {
    unsafe { read_volatile((u32::from(base) + 4) as *const u8) }
}

fn write_leds(_cs: CriticalSection, base: GpioBase, val: u8) {
    unsafe { write_volatile(u32::from(base) as *mut u8, val) }
}

#[no_mangle]
#[allow(non_snake_case)]
extern "C" fn MachineExternal() {
    // SAFETY: Interrupts are disabled.
    let cs = unsafe { CriticalSection::new() };
    let timer = unsafe { TIMER_BASE.assume_init() };
    let ser = unsafe { SERIAL_BASE.assume_init() };

    if (read_timer_int(cs, timer) & 0x01) != 0 {
        // Interrupts 12000000/16834, or ~764 times per second.
        COUNT.fetch_add(1, SeqCst);
    }

    let ser_int = read_serial_int(cs, ser);
    if (ser_int & 0x01) != 0 {
        let rx = read_serial_rx(cs, ser);
        RX.borrow(cs).set(Some(rx));
    }

    if (ser_int & 0x02) != 0 {
        let maybe_queue = {
            // SAFETY: No other thread ever touches this. We cannot reach this
            // line before main finishes initializing this var. Thus, this
            // is the only &mut released to safe code.
            let cons = unsafe { TX_CONS.assume_init_mut() };
            cons.dequeue()
        };

        if TX_IN_PROGRESS.load(SeqCst) {
            match maybe_queue {
                Some(tx) => {
                    write_serial_tx(cs, ser, tx);
                }
                None => TX_IN_PROGRESS.store(false, SeqCst),
            }
        }
    }

    // For debugging.
    // unsafe {
    //     // Clear MPIE so we go back to previous interrupt state.
    //     let bits: usize = 1 << 7;
    //     core::arch::asm!(concat!("csrrc x0, mstatus, {0}"), in(reg) bits)
    //  };
}

fn write_char<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>, utf8_char: char) {
    let mut buf = [0; 4];

    for b in utf8_char.encode_utf8(&mut buf).as_bytes() {
        let mut queue_full = true;
        while queue_full {
            queue_full = critical_section::with(|cs| {
                if TX_IN_PROGRESS.load(SeqCst) {
                    tx_prod.enqueue(*b).is_err()
                } else {
                    write_serial_tx(cs, ser, *b);
                    TX_IN_PROGRESS.store(true, SeqCst);
                    false
                }
            });
        }
    }
}

fn write_line<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>, line: &str) {
    for c in line.chars() {
        write_char(ser, tx_prod, c);
    }
}

struct ReadNumError {}

fn read_num<const N: usize>(
    ser: SerialBase,
    tx_prod: &mut Producer<u8, N>,
) -> Result<u8, ReadNumError> {
    let mut buf = [0; 3];
    let mut cnt = 0;

    while cnt < 3 {
        critical_section::with(|cs| {
            if let Some(b) = RX.borrow(cs).get() {
                buf[cnt] = b;
                write_char(ser, tx_prod, b as char);

                cnt += 1;

                RX.borrow(cs).set(None);
            }
        });
    }

    let (num, valid) = u8::from_radix_10(&buf);

    if valid > 0 {
        Ok(num)
    } else {
        Err(ReadNumError {})
    }
}

type RuleBuf = BitArr!(for BUFSIZ, in u8, Msb0);

fn do_demo<const N: usize>(
    ser: SerialBase,
    tx_prod: &mut Producer<u8, N>,
    gpio: GpioBase,
    rule: u8,
) {
    const BOX_DRAW_CHAR_MAP: [char; 8] = [
        ' ', '\u{2591}', '\u{2591}', '\u{2592}', '\u{2592}', '\u{2593}', '\u{2588}', '\u{2588}',
    ];
    const DONUT_CHAR_MAP: [char; 8] = [' ', '.', '-', ':', ';', '!', '#', '@']; // https://www.a1k0n.net/2011/07/20/donut-math.html

    // Alternate unshaded drawing chars
    const BOX_DRAW_CHAR_BASIC: char = '\u{2588}';
    const DONUT_CHAR_BASIC: char = '#'; // https://www.a1k0n.net/2011/07/20/donut-math.html
    const EMPTY_CHAR_BASIC: char = ' ';
    const CHAR_MAPS: [&[char; 8]; 2] = [&BOX_DRAW_CHAR_MAP, &DONUT_CHAR_MAP];

    // Convert from raw value (used for coloring) to what rule 110 expects.
    let raw_map: BitArray<[u8; 1], Lsb0> = BitArray::from([rule; 1]);
    let mut char_map_idx = 0;
    let mut curr_char_map = Some(CHAR_MAPS[char_map_idx]);

    let mut buffer: RuleBuf = BitArray::ZERO;
    *buffer.get_mut(INIT_POS).unwrap() = true; // Initialize with an interesting value.

    // Print initial row. Ignore actual adjacent cell values. Mildly cheating
    // a bit!
    for i in 0..BUFSIZ {
        if buffer[i] {
            // We always reset to BOX_DRAW_CHAR_MAP.
            write_char(ser, tx_prod, BOX_DRAW_CHAR_BASIC);
        } else {
            write_char(ser, tx_prod, EMPTY_CHAR_BASIC);
        }
    }

    write_char(ser, tx_prod, '\n');

    loop {
        let mut prev_left = false; // Left boundary is 0.
        let mut prev_center = buffer[0]; // Calculate column 0 first.

        for i in 0..BUFSIZ {
            let prev_right = buffer.get(i + 1).as_deref().copied().unwrap_or(false); // Right boundary is 0.
            let idx = 4 * u8::from(prev_left) + 2 * u8::from(prev_center) + u8::from(prev_right);

            // Write each column in the previous row first.

            let shade = curr_char_map.map_or_else(
                || {
                    if raw_map[idx as usize] {
                        if char_map_idx % 2 == 0 {
                            BOX_DRAW_CHAR_BASIC
                        } else {
                            DONUT_CHAR_BASIC
                        }
                    } else {
                        EMPTY_CHAR_BASIC
                    }
                },
                |cm| cm[idx as usize],
            );
            write_char(ser, tx_prod, shade);

            // Prepare the current row to be written on next iteration of
            // outer loop.
            buffer.set(i, raw_map[idx as usize]);

            prev_left = prev_center;
            prev_center = prev_right;
        }

        // Next row.
        write_char(ser, tx_prod, '\n');

        COUNT.store(0, SeqCst);

        // SAFETY: Not accessed in an interrupt context.
        let cs = unsafe { CriticalSection::new() };
        let mut debounce_chk_passed = (read_inp_port(cs, gpio) & 0x01) != 0;

        // Wait ~ 1/5th of a second
        while COUNT.load(SeqCst) < 144 {
            if debounce_chk_passed
                && read_inp_port(cs, gpio) & (read_inp_port(cs, gpio) & 0x01) == 0
            {
                debounce_chk_passed = false;
            }
        }

        if debounce_chk_passed {
            char_map_idx = (char_map_idx + 1) % 4;
            curr_char_map = CHAR_MAPS.get(char_map_idx).map(|v| &**v);
        }

        let ctrl_c = critical_section::with(|cs| match RX.borrow(cs).get() {
            Some(0x03) => {
                RX.borrow(cs).set(None);
                true
            }
            Some(_) => {
                RX.borrow(cs).set(None);
                false
            }
            _ => false,
        });

        if ctrl_c {
            return;
        }
    }
}

fn set_rule<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>, gpio: GpioBase) -> u8 {
    write_line(ser, tx_prod, "ctrl-c hit\nrule (default 110)? ");

    let rule = read_num(ser, tx_prod).unwrap_or(110);

    // SAFETY: Not accessed in an interrupt context.
    let cs = unsafe { CriticalSection::new() };
    write_leds(cs, gpio, rule);

    write_char(ser, tx_prod, '\n');

    rule
}


#[entry]
#[allow(missing_docs)]
fn main() -> ! {
    // SAFETY: Interrupts are disabled.
    let queue: &'static mut Queue<u8, 64> = {
        static mut Q: Queue<u8, 64> = Queue::new();
        unsafe { &mut *addr_of_mut!(Q) }
    };
    let (mut tx_prod, consumer) = queue.split();
    unsafe { TX_CONS.write(consumer) };

    let gpio: GpioBase;
    let timer: TimerBase;
    let ser: SerialBase;

    // SAFETY: Interrupts are disabled.
    unsafe {
        (gpio, timer, ser) = io_addrs::get_bases();
        GPIO_BASE.write(gpio);
        TIMER_BASE.write(timer);
        SERIAL_BASE.write(ser);

        mstatus::set_mie();
        mie::set_mext();
    }

    // App begins here.
    let mut rule = 110;

    loop {
        do_demo(ser, &mut tx_prod, gpio, rule);
        rule = set_rule(ser, &mut tx_prod, gpio);
    }
}
