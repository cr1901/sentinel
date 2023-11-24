#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::ptr::{write_volatile, read_volatile};
use core::cell::Cell;
use critical_section::{self, Mutex};


#[derive(Clone, Copy)]
enum TxState {
    Full(u8),
    Sending,
    Empty
}


static RX: Mutex<Cell<Option<u8>>> = Mutex::new(Cell::new(None));
static TX: Mutex<Cell<TxState>> = Mutex::new(Cell::new(TxState::Empty));
static TIMER: Mutex<Cell<bool>> = Mutex::new(Cell::new(false));
static COUNT: Mutex<Cell<u8>> = Mutex::new(Cell::new(0));


#[no_mangle]
#[allow(non_snake_case)]
fn MachineExternal() {
    let tim_int: u8 = unsafe { read_volatile(0x04000000 as *const u8) };

    if (tim_int & 0x01) != 0 {
        critical_section::with(|cs| {
            let mut cnt = COUNT.borrow(cs).get();
            cnt += 1;

            // Interrupts 12000000/16834, or ~732 times per second. Tone it
            // down to 1/10th of a second.
            if cnt == 73 {
                cnt = 0;
                TIMER.borrow(cs).set(true);
            }

            COUNT.borrow(cs).set(cnt);
        });
    }

    let mut ser_int = unsafe { read_volatile(0x06000001 as *const u8) };
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

        match maybe_tx {
            TxState::Full(tx) => unsafe { 
                write_volatile(0x06000000 as *mut u8, tx);
                critical_section::with(|cs| {
                    TX.borrow(cs).set(TxState::Sending);
                });        
            },
            TxState::Sending => {
                critical_section::with(|cs| {
                    TX.borrow(cs).set(TxState::Empty);
                });
            }
            TxState::Empty => {}
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
    unsafe {
        mstatus::set_mie();
        mie::set_mext();
    }

    unsafe { write_volatile(0x06000000 as *mut u8, 'A' as u8); }
    // do something here
    loop {
       critical_section::with(|cs| {
            match RX.borrow(cs).get() {
                Some(rx) => unsafe {
                    match TX.borrow(cs).get() {
                        TxState::Full(_) => {},
                        TxState::Sending => {
                            TX.borrow(cs).set(TxState::Full(rx));
                            // TX handler will run when finished sending.
                        }
                        TxState::Empty => {
                            write_volatile(0x06000000 as *mut u8, rx);
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
                    TxState::Full(_) => {},
                    TxState::Sending => {
                        TX.borrow(cs).set(TxState::Full('T' as u8));
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
        }); 
    }
}
