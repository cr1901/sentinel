#![no_std]
#![no_main]

use panic_halt as _;
use riscv_rt::entry;
use core::ptr::write_volatile;

#[entry]
fn main() -> ! {
    unsafe { write_volatile(0x06000000 as *mut u8, 'A' as u8); }
    // do something here
    loop {
    }
}
