#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::ptr::{write_volatile, read_volatile};
use core::cell::{Cell, UnsafeCell};
use critical_section::{self, Mutex};
use heapless::spsc::{Queue, Consumer};


#[derive(Clone, Copy)]
enum TxState {
    Sending,
    Empty
}

static RX: Mutex<Cell<Option<u8>>> = Mutex::new(Cell::new(None));
static TX: Mutex<Cell<TxState>> = Mutex::new(Cell::new(TxState::Empty));
static TIMER: Mutex<Cell<bool>> = Mutex::new(Cell::new(false));
static COUNT: Mutex<Cell<u8>> = Mutex::new(Cell::new(0));
// SAFETY: Emulating a "Send". We never touch this from non interrupt thread
// once this is set.
static TX_FIFO_C: Mutex<UnsafeCell<Option<Consumer<'static, u8, 64>>>> = Mutex::new(UnsafeCell::new(None));


// `read/write_volatile` SAFETYs: Interrupts are disabled, valid I/O port
// addresses.

#[no_mangle]
#[allow(non_snake_case)]
fn MachineExternal() {
    let tim_int: u8 = unsafe { read_volatile(0x04000000 as *const u8) };

    if (tim_int & 0x01) != 0 {
        critical_section::with(|cs| {
            let mut cnt = COUNT.borrow(cs).get();
            cnt += 1;

            // Interrupts 12000000/16834, or ~764 times per second. Tone it
            // down to 1/10th of a second.
            if cnt == 73 {
                cnt = 0;
                TIMER.borrow(cs).set(true);
            }

            COUNT.borrow(cs).set(cnt);
        });
    }

    let ser_int = unsafe { read_volatile(0x06000001 as *const u8) };
    if (ser_int & 0x01) != 0 {
        let rx = unsafe { read_volatile(0x06000000 as *const u8) };
        critical_section::with(|cs| {
            RX.borrow(cs).set(Some(rx));
        });
    }

    if (ser_int & 0x02) != 0 {
        let maybe_tx = critical_section::with(|cs| {
            TX.borrow(cs).get()
        });

        let maybe_queue = critical_section::with(|cs| {
            // SAFETY: No other thread ever touches this. We cannot reach this
            // line before main finishes initializing this var.
            let cons = unsafe { (&mut *TX_FIFO_C.borrow(cs).get()).as_mut().unwrap() };
            cons.dequeue()
        });

        match (maybe_tx, maybe_queue) {
            (TxState::Sending, Some(tx)) => {
                unsafe { write_volatile(0x06000000 as *mut u8, tx) };
            }
            (TxState::Sending, None) => {
                critical_section::with(|cs| {
                    TX.borrow(cs).set(TxState::Empty);
                });
            },
            (TxState::Empty, _) => {}
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
    let (mut producer, consumer) = queue.split();
    critical_section::with(|cs| {
        unsafe { *TX_FIFO_C.borrow(cs).get() = Some(consumer) };
    });

    // SAFETY: Interrupts are disabled.
    unsafe {
        mstatus::set_mie();
        mie::set_mext();
    }

    unsafe { write_volatile(0x06000000 as *mut u8, 'A' as u8); }
    // do something here
    loop {
       critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(rx) => {
                    match TX.borrow(cs).get() {
                        TxState::Sending => {
                            producer.enqueue(rx);
                            // TX handler will run when finished sending.
                        }
                        TxState::Empty => {
                            unsafe { write_volatile(0x06000000 as *mut u8, rx) };
                            TX.borrow(cs).set(TxState::Sending);
                            // TX handler will run when finished sending.
                        }
                    }

                    RX.borrow(cs).set(None);
                },
                None => {}
            }

            if TIMER.borrow(cs).get() {
                match TX.borrow(cs).get() {
                    TxState::Sending => {
                        producer.enqueue('T' as u8);
                        // TX handler will run when finished sending.
                    },
                    TxState::Empty => {
                        unsafe { write_volatile(0x06000000 as *mut u8, 'T' as u8) };
                        TX.borrow(cs).set(TxState::Sending);
                        // TX handler will run when finished sending.
                    }
                }

                TIMER.borrow(cs).set(false);
            }

            // Mirror the input port to the LEDs.
            let inp = unsafe { read_volatile(0x02000000 as *const u8) };
            unsafe { write_volatile(0x02000000 as *mut u8, inp) };
        }); 
    }
}
