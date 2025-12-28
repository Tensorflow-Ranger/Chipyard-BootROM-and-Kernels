# RISC-V S-Mode Multi-Process Kernel
# Based on the user's trusted code base.

.section .text
.global _start

# --- Constants ---
.equ SATP_MODE_SV39, 8 << 60
.equ SSTATUS_SIE,  1 << 1
.equ SSTATUS_SPIE, 1 << 5
.equ SSTATUS_SPP,  1 << 8
.equ SIE_STIE,     1 << 5
.equ SCAUSE_TIMER, 0x8000000000000005
.equ PAGE_SIZE, 4096
.equ PTE_V, 1 << 0
.equ PTE_R, 1 << 1
.equ PTE_W, 1 << 2
.equ PTE_X, 1 << 3

# --- Boot and Setup ---
_start:
    # Delegate traps to S-Mode
    li t0, -1
    csrw mideleg, t0
    csrw medeleg, t0
    
    # Disable interrupts during setup
    csrci sstatus, SSTATUS_SIE
    
    # Set up all page tables
    call setup_paging
    
    # Set up trap handler
    la t0, supervisor_trap_handler
    csrw stvec, t0
    
    # Initialize process contexts
    call init_processes
    
    # Enable supervisor timer interrupts
    li t0, SIE_STIE
    csrw sie, t0
    
    # Set first timer interrupt (for QEMU virt machine)
    rdtime a0
    li a1, 1000000
    add a0, a0, a1
    li t0, 0x200bff8 # CLINT base address
    sd a0, 0(t0)
    
    # Enable interrupts globally
    csrs sstatus, SSTATUS_SIE
    
    # Start the first process
    call schedule
    
idle_loop:
    wfi
    j idle_loop

# --- Paging and Memory Setup ---
# Fixed clear_loop that won't get stuck
setup_paging:
    # Clear all 8 page tables (safer approach)
    la t0, proc1_l2_table
    li t1, PAGE_SIZE * 8 / 8  # Number of 8-byte words to clear
    li t2, 0
clear_loop:
    sd t2, 0(t0)
    addi t0, t0, 8
    addi t1, t1, -1           # Decrement word count, not byte count
    bnez t1, clear_loop

    # Alternative safer version using end address comparison:
    # la t0, proc1_l2_table
    # la t1, proc2_stack_page    # End of all our tables
    # li t2, 0
    # clear_loop_alt:
    #     sd t2, 0(t0)
    #     addi t0, t0, 8
    #     blt t0, t1, clear_loop_alt

    # Rest of setup_paging continues as before...
    # Manually copy process code into their dedicated physical pages
    la t0, user_prog1_template
    la t1, proc1_code_page
    li t2, 32
copy_loop_1:
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    addi t2, t2, -4
    bnez t2, copy_loop_1

    la t0, user_prog2_template
    la t1, proc2_code_page
    li t2, 32
copy_loop_2:
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    addi t2, t2, -4
    bnez t2, copy_loop_2
    
    fence.i

    # --- Configure Page Tables for Process 1 ---
    la t0, proc1_l2_table
    la t1, proc1_l1_kernel
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V
    sd t1, 16(t0)
    
    la t1, proc1_l1_data
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V
    sd t1, 0(t0)
    
    la t0, proc1_l1_kernel
    li t1, 0x80000000 >> 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_W | PTE_X
    sd t1, 0(t0)
    
    la t0, proc1_l1_data
    la t1, proc1_code_page
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_X
    sd t1, 512(t0)  # Virtual address 0x10000000 maps here
    
    la t1, proc1_stack_page
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_W
    sd t1, 544(t0)  # Virtual address 0x11000000 maps here

    # --- Configure Page Tables for Process 2 ---
    la t0, proc2_l2_table
    la t1, proc2_l1_kernel
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V
    sd t1, 16(t0)
    
    la t1, proc2_l1_data
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V
    sd t1, 0(t0)
    
    la t0, proc2_l1_kernel
    li t1, 0x80000000 >> 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_W | PTE_X
    sd t1, 0(t0)
    
    la t0, proc2_l1_data
    la t1, proc2_code_page
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_X
    sd t1, 512(t0)
    
    la t1, proc2_stack_page
    srli t1, t1, 12
    slli t1, t1, 10
    ori t1, t1, PTE_V | PTE_R | PTE_W
    sd t1, 544(t0)
    
    # Enable Paging using Process 1's map to start
    la t0, proc1_l2_table
    srli t0, t0, 12
    li t1, SATP_MODE_SV39
    or t0, t0, t1
    csrw satp, t0
    sfence.vma
    ret
    
# --- Process Management ---
init_processes:
    # Context: 0=sepc, 8=sp, 16=sstatus, 24=satp
    la t0, processes
    # Proc 1
    li t1, 0x10000000; sd t1, 0(t0)
    li t1, 0x11000000 + PAGE_SIZE; sd t1, 8(t0)
    li t1, SSTATUS_SPP | SSTATUS_SPIE; sd t1, 16(t0)
    la t1, proc1_l2_table; srli t1, t1, 12; li t2, SATP_MODE_SV39; or t1, t1, t2; sd t1, 24(t0)
    # Proc 2
    addi t0, t0, 256
    li t1, 0x10000000; sd t1, 0(t0)
    li t1, 0x11000000 + PAGE_SIZE; sd t1, 8(t0)
    li t1, SSTATUS_SPP | SSTATUS_SPIE; sd t1, 16(t0)
    la t1, proc2_l2_table; srli t1, t1, 12; li t2, SATP_MODE_SV39; or t1, t1, t2; sd t1, 24(t0)
    # Set current proc to 0
    li t0, 0; la t1, current_process; sw t0, 0(t1)
    ret

# --- Scheduler and Context Switch ---
schedule:
    # Save context of OLD process
    la t0, current_process
    lw t1, 0(t0)
    la t2, processes; li t3, 256; mul t3, t1, t3; add t2, t2, t3
    csrr t3, sepc; sd t3, 0(t2)
    csrr t3, sstatus; sd t3, 16(t2)
    sd sp, 8(t2)

    # Choose NEXT process (toggle 0/1)
    li t3, 1; sub t1, t3, t1; sw t1, 0(t0)

    # Load context of NEW process
    la t2, processes; li t3, 256; mul t3, t1, t3; add t2, t2, t3
    ld t3, 24(t2); csrw satp, t3; sfence.vma
    ld t3, 16(t2); csrw sstatus, t3
    ld t3, 0(t2); csrw sepc, t3
    ld sp, 8(t2)
    sret

# --- Trap Handling ---
supervisor_trap_handler:
    # Switch to a safe kernel stack
    mv t5, sp
    la sp, kernel_stack_top
    
    csrr t0, scause
    li t1, SCAUSE_TIMER
    beq t0, t1, handle_timer_interrupt
    
    # Unknown trap, just restore sp and return
    mv sp, t5
    sret
    
handle_timer_interrupt:
    # Reset timer
    rdtime a0; li a1, 1000000; add a0, a0, a1
    li t0, 0x200bff8; sd a0, 0(t0)
    # Ack interrupt
    li t0, SIE_STIE; csrc sip, t0
    # Context switch
    call schedule

# --- Process Code Templates ---
.align 4
user_prog1_template:
    li a0, 1; 1: j 1b
user_prog2_template:
    li a0, 2; 1: j 1b

# --- Data Section ---
.section .data
.align 12
# Page Tables for Proc 1
proc1_l2_table: .space 4096
proc1_l1_kernel: .space 4096
proc1_l1_data: .space 4096
# Page Tables for Proc 2
proc2_l2_table: .space 4096
proc2_l1_kernel: .space 4096
proc2_l1_data: .space 4096
# Process Contexts (256 bytes each)
.align 8
processes: .space 512
current_process: .word 0

# --- BSS Section (Zero-Initialized Data) ---
.section .bss
.align 12
kernel_stack_bottom: .space 4096
kernel_stack_top:
proc1_code_page: .space 4096
proc1_stack_page: .space 4096
proc2_code_page: .space 4096
proc2_stack_page: .space 4096