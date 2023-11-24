#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use riscv::register::{mie, mstatus};
use core::ptr::{write_volatile, read_volatile};
use core::cell::Cell;
use critical_section::{self, Mutex};


static INTERRUPT: Mutex<Cell<bool>> = Mutex::new(Cell::new(false));

#[no_mangle]
fn MachineExternal() {
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
        }); 
    }
}
