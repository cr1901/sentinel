#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::mem::MaybeUninit;
use core::ptr::{write_volatile, read_volatile};
use core::cell::Cell;
use critical_section::{self, Mutex, CriticalSection};
use heapless::spsc::{Queue, Consumer};
use portable_atomic::{AtomicBool, AtomicU8, Ordering::SeqCst};


static RX: Mutex<Cell<Option<u8>>> = Mutex::new(Cell::new(None));
static TX_IN_PROGRESS: AtomicBool = AtomicBool::new(false);
static TIMER: AtomicBool = AtomicBool::new(false);
static COUNT: AtomicU8 = AtomicU8::new(0);
// SAFETY: Emulating a "Send". We never touch this from non interrupt thread
// once this is set.
static mut TX_CONS: MaybeUninit<Consumer<'static, u8, 64>> = MaybeUninit::uninit();

// It is difficult to get CSR and Wishbone periphs to share the same addresses,
// so I don't bother. Instead, use base u32s to access hardware, so that the
// same firmware can be used regardless of board.
pub mod io_addrs {
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
        let cnt = COUNT.fetch_add(1, SeqCst);

        // Interrupts 12000000/16834, or ~764 times per second. Tone it
        // down to 1/10th of a second.
        if cnt == 72 {
            COUNT.store(0, SeqCst);
            TIMER.store(true, SeqCst)
        }
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

#[entry]
fn main() -> ! {
    // SAFETY: Interrupts are disabled.
    let queue: &'static mut Queue<u8, 64> = {
        static mut Q: Queue<u8, 64> = Queue::new();
        unsafe { &mut Q }
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

    critical_section::with(|cs| {
        write_serial_tx(cs, ser, 'A' as u8)
    });

    // do something here
    let mut i = 0;
    let mut toggle = false;

    loop {
       critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(rx) => {
                    if TX_IN_PROGRESS.load(SeqCst) {
                        let _ = tx_prod.enqueue(rx);
                    } else {
                        write_serial_tx(cs, ser, rx);
                        TX_IN_PROGRESS.store(true, SeqCst)
                    }

                    RX.borrow(cs).set(None);
                },
                None => {}
            }

            if TIMER.load(SeqCst) {
                if TX_IN_PROGRESS.load(SeqCst) {
                    let _ = tx_prod.enqueue('T' as u8);
                } else {
                    write_serial_tx(cs, ser, 'T' as u8);
                    TX_IN_PROGRESS.store(true, SeqCst)
                }

                i += 1;
                TIMER.store(false, SeqCst);
                if i >= 5 {
                    toggle = !toggle;
                    i = 0;
                }
            }

            // Mirror the low 2 bits of the I/O to the LEDs. Defaults to
            // in at reset.
            let inp = read_inp_port(cs, gpio) & 0x03;
            let toggle_led = (toggle as u8) << 2;
            let tx_len = (tx_prod.len() as u8) << 3;
            write_leds(cs, gpio, tx_len | toggle_led | inp);
        }); 
    }
}
