/*! Example Rust application for AttoSoC Sentinel SoC.

[Rule 110](https://en.wikipedia.org/wiki/Rule_110) demo using the UART as an
output medium.
    
*/

#![no_std]
#![no_main]

use bitvec::field::BitField;
use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::char::from_digit;
use core::mem::MaybeUninit;
use core::ptr::{write_volatile, read_volatile, addr_of_mut};
use core::cell::Cell;
use core::str;
use critical_section::{self, Mutex, CriticalSection};
use heapless::spsc::{Queue, Producer, Consumer};
use portable_atomic::{AtomicBool, AtomicU8, Ordering::SeqCst};
use bitvec::prelude::*;
use atoi::FromRadix10;


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

    #[derive(Clone, Copy)]
    pub struct GpioBase(u32);

    impl From<GpioBase> for u32 {
        fn from(value: GpioBase) -> Self {
            value.0
        }
    }

    #[derive(Clone, Copy)]
    pub struct TimerBase(u32);

    impl From<TimerBase> for u32 {
        fn from(value: TimerBase) -> Self {
            value.0
        }
    }

    #[derive(Clone, Copy)]
    pub struct SerialBase(u32);

    impl From<SerialBase> for u32 {
        fn from(value: SerialBase) -> Self {
            value.0
        }
    }

    // SAFETY: Must be called when interrupts are disabled.
    pub unsafe fn get_bases() -> (GpioBase, TimerBase, SerialBase) {
        // If IRQ is pending after reset, we are using WBSerial, and thus a
        // wishbone peripheral bus.
        if mip::read().mext() {
            return (GpioBase(0x02000000), TimerBase(0x40000000),
                    SerialBase(0x80000000));
        } else {
            return (GpioBase(0x02000000), TimerBase(0x02800000),
                    SerialBase(0x03000000));
        }
    }
}

pub use io_addrs::{GpioBase, TimerBase, SerialBase};

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
fn MachineExternal() {
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
        critical_section::with(|cs| {
            RX.borrow(cs).set(Some(rx));
        });
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
                None => {
                    TX_IN_PROGRESS.store(false, SeqCst) 
                },
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
            queue_full  = critical_section::with(|cs| {
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

fn read_num<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>) -> Result<u8, ReadNumError> {
    let mut buf = [0; 3];
    let mut cnt = 0;

    while cnt < 3 {
        critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(b) =>  {
                    buf[cnt] = b;
                    write_char(ser, tx_prod, b as char);
                    
                    cnt += 1;
    
                    RX.borrow(cs).set(None);
                },
                None => {
                    /* Drop non-ASCII digits. */
                },
            }
        });
    }

    let (num, valid) = u8::from_radix_10(&buf);

    if valid > 0 {
        return Ok(num)
    } else {
        return Err(ReadNumError {})
    }
}


fn do_demo<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>, rule: u8) {
    const UTF8_CHAR_MAP: [char; 8] = [' ', '\u{2591}', '\u{2591}', '\u{2592}',
        '\u{2592}', '\u{2593}', '\u{2588}', '\u{2588}'];
    // Alternate character maps:
    // const UTF8_CHAR_MAP: [char; 8] = [' ', '\u{2588}', '\u{2588}', '\u{2588}',
    //     ' ', '\u{2588}', '\u{2588}', ' '];
    // const UTF8_CHAR_MAP: [u8; 8] = [b' ', b'.', b'-', b':', b';', b'!', b'#', b'@']; // https://www.a1k0n.net/2011/07/20/donut-math.html
    // const UTF8_CHAR_MAP: [u8; 8] = [b' ', b'#', b'#', b'#', b' ', b'#', b'#', b' ']; // https://www.a1k0n.net/2011/07/20/donut-math.html

    // Convert from raw value (used for coloring) to what rule 110 expects.
    let raw_map: BitArray<[u8; 1], Lsb0> = BitArray::from([rule; 1]);

    let mut buffer: RuleBuf = BitArray::ZERO;
    *buffer.last_mut().unwrap() = true; // Initialize with an interesting value.
    // *buffer.get_mut(40).unwrap() = true;

    // Print initial row. Ignore actual adjacent cell values. Mildly cheating
    // a bit!
    for i in 0..BUFSIZ {
        if buffer[i] {
            write_char(ser, tx_prod, UTF8_CHAR_MAP.get(6).copied().unwrap() as char);
        } else {
            write_char(ser, tx_prod, ' ');
        }
    }

    write_char(ser, tx_prod, '\n');

    loop {
        let mut prev_left = false; // Left boundary is 0.
        let mut prev_center = buffer[0]; // Calculate column 0 first.
    
        for i in 0..BUFSIZ {
            let prev_right = buffer.get(i + 1).as_deref().copied().unwrap_or(false);  // Right boundary is 0.
            let idx = 4 * prev_left as u8 + 2 * prev_center as u8 + prev_right as u8;

            // Write each column in the previous row first.
            let shade = UTF8_CHAR_MAP[idx as usize];
            write_char(ser, tx_prod, shade as char);

            // Prepare the current row to be written on next iteration of
            // outer loop.
            buffer.set(i as usize, raw_map[idx as usize]);

            prev_left = prev_center;
            prev_center = prev_right;
        }

        // Next row.
        write_char(ser, tx_prod, '\n');

        COUNT.store(0, SeqCst);

        // Wait ~ 1/5th of a second
        while COUNT.load(SeqCst) < 144 {

        }

        let ctrl_c = critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(t) if t == 0x03 => {
                    RX.borrow(cs).set(None);
                    true
                }
                Some(_) => {
                    RX.borrow(cs).set(None);
                    false
                }
                _ => false
            }
        });

        if ctrl_c {
            return;
        }
    }
}

fn set_rule<const N: usize>(ser: SerialBase, tx_prod: &mut Producer<u8, N>, gpio: GpioBase) -> u8 {
    write_line(ser, tx_prod, "ctrl-c hit\nrule (default 110)? ");

    let rule = read_num(ser, tx_prod).unwrap_or(110);

    critical_section::with(|cs| {
        write_leds(cs, gpio, rule);
    });
    write_char(ser, tx_prod, '\n');

    rule
}

const BUFSIZ: usize = 80;
type RuleBuf = BitArr!(for BUFSIZ, in u8, Msb0);

enum State {
    Read,
    Demo
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
    let mut state = State::Demo;
    let mut rule = 110;

    loop {
        do_demo(ser, &mut tx_prod, rule);
        rule = set_rule(ser, &mut tx_prod, gpio);
    }
}
