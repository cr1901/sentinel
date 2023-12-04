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


// `read/write_volatile` SAFETYs: We have a CriticalSection, which means we've
// proven that we have exclusive access or have opted into unsafety previously.
// These are all valid I/O port addresses.
fn read_timer_int(_cs: CriticalSection) -> u8 {
    unsafe { read_volatile(0x40000000 as *const u8) }
}

fn read_serial_int(_cs: CriticalSection) -> u8 {
    unsafe { read_volatile(0x80000001 as *const u8) }
}

fn read_serial_rx(_cs: CriticalSection) -> u8 {
    unsafe { read_volatile(0x80000000 as *const u8) }
}

fn write_serial_tx(_cs: CriticalSection, val: u8) {
    unsafe { write_volatile(0x80000000 as *mut u8, val) }
}

fn read_inp_port(_cs: CriticalSection,) -> u8 {
    unsafe { read_volatile(0x02000000 as *const u8) }
}

fn write_leds(_cs: CriticalSection, val: u8) {
    unsafe { write_volatile(0x02000000 as *mut u8, val) }
}

#[no_mangle]
#[allow(non_snake_case)]
fn MachineExternal() {
    // SAFETY: Interrupts are disabled.
    let cs = unsafe { CriticalSection::new() };

    if (read_timer_int(cs) & 0x01) != 0 {
        let cnt = COUNT.fetch_add(1, SeqCst);

        // Interrupts 12000000/16834, or ~764 times per second. Tone it
        // down to 1/10th of a second.
        if cnt == 72 {
            COUNT.store(0, SeqCst);
            TIMER.store(true, SeqCst)
        }
    }

    let ser_int = read_serial_int(cs);
    if (ser_int & 0x01) != 0 {
        let rx = read_serial_rx(cs);
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
                    write_serial_tx(cs, tx);
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

    // SAFETY: Interrupts are disabled.
    unsafe {
        mstatus::set_mie();
        mie::set_mext();
    }

    critical_section::with(|cs| {
        write_serial_tx(cs, 'A' as u8)
    });

    // do something here
    loop {
       critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(rx) => {
                    if TX_IN_PROGRESS.load(SeqCst) {
                        let _ = tx_prod.enqueue(rx);
                    } else {
                        write_serial_tx(cs, rx);
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
                    write_serial_tx(cs, 'T' as u8);
                    TX_IN_PROGRESS.store(true, SeqCst)
                }

                TIMER.store(false, SeqCst);
            }

            // Mirror the input port to the LEDs.
            let inp = read_inp_port(cs);
            let tx_len = (tx_prod.len() as u8) << 2;
            write_leds(cs, tx_len | inp);
        }); 
    }
}
