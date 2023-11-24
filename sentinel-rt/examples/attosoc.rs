#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::ptr::{write_volatile, read_volatile};
use core::cell::Cell;
use critical_section::{self, Mutex};


static INTERRUPT: Mutex<Cell<bool>> = Mutex::new(Cell::new(false));
static TIMER: Mutex<Cell<bool>> = Mutex::new(Cell::new(false));
static COUNT: Mutex<Cell<u8>> = Mutex::new(Cell::new(0));


#[no_mangle]
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

    let ser_int = unsafe { read_volatile(0x06000001 as *const u8) };

    if (ser_int & 0x01) != 0 {
        unsafe { read_volatile(0x06000000 as *const u8) };
        critical_section::with(|cs| {
            INTERRUPT.borrow(cs).set(true);
        });

        unsafe { write_volatile(0x06000001 as *mut u8, ser_int & 0xFE) };
    }

    if (ser_int & 0x02) != 0 {
        unsafe { write_volatile(0x06000001 as *mut u8, ser_int & 0b11111101) };
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
            if INTERRUPT.borrow(cs).get() {
                unsafe { write_volatile(0x06000000 as *mut u8, 'I' as u8); }
                INTERRUPT.borrow(cs).set(false)
            }

            if TIMER.borrow(cs).get() {
                unsafe { write_volatile(0x06000000 as *mut u8, 'T' as u8); }
                TIMER.borrow(cs).set(false)
            }
        }); 
    }
}
