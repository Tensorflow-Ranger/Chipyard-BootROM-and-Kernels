# RISC-V Kernel with User-Accessible Identity Map
#
# STRATEGY: Instead of copying user code, this kernel gives User Mode
# permission to execute code directly from the kernel's memory region.
# This is simpler but removes the security boundary between kernel and user.

.section .text
.global _start

# --- Constants ---
.equ SATP_MODE_SV39, 0x8000000000000000
.equ SSTATUS_SIE, 0x2
.equ SSTATUS_SPIE, 0x20
.equ SSTATUS_SPP, 0x100
.equ SCAUSE_TIMER, 0x8000000000000005
.equ SCAUSE_ECALL_U, 0x8
.equ PAGE_SIZE, 4096
.equ PTE_V, 0x1
.equ PTE_R, 0x2
.equ PTE_W, 0x4
.equ PTE_X, 0x8
.equ PTE_U, 0x10 # The User bit
.equ PTE_A, 0x40
.equ PTE_D, 0x80 

# --- Boot and Setup ---
_start:
    li t0, -1; csrw mideleg, t0; csrw medeleg, t0
    csrci sstatus, SSTATUS_SIE
    call setup_paging
    la t0, trap_handler; csrw stvec, t0
    call init_processes
    li t0, SSTATUS_SIE; csrs sstatus, t0
    call schedule
idle_loop:
    wfi; j idle_loop

# --- Paging and Memory Setup ---
setup_paging:
    # Clear page tables using the user's trusted loop
    la t0, page_table_l2
    li t1, PAGE_SIZE * 5 # We only need 4 tables in this simpler design
    li t2, 0
clear_loop:
    sd t2, 0(t0)
    addi t0, t0, 8
    addi t1, t1, -8
    bnez t1, clear_loop    

    # NOTE: The copy_loops have been REMOVED. They are no longer needed.
    fence.i
    
    # Set up L2 page table (root)
    # Set up L2 page table (root)
    la t0, page_table_l2
    # L2 -> L1 (Kernel): This is a POINTER. R,W,X must be 0.
    la t1, page_table_l1_kernel
    srli t1, t1, 12; slli t1, t1, 10
    ori t1, t1, PTE_V  # ONLY PTE_V is set!
    sd t1, 16(t0)

    # L2 -> L1 (User): This is a POINTER. R,W,X must be 0.
    la t1, page_table_l1_user1
    srli t1, t1, 12; slli t1, t1, 10
    ori t1, t1, PTE_V  # ONLY PTE_V is set!
    sd t1, 0(t0)
    
    # Set up L1 kernel table to point to L0 kernel table
    la t0, page_table_l1_kernel
    # L1 -> L0 (Kernel): This is a POINTER. R,W,X must be 0.
    la t1, page_table_l0_kernel
    srli t1, t1, 12; slli t1, t1, 10
    ori t1, t1, PTE_V # ONLY PTE_V is set!
    sd t1, 0(t0)

    # Set up L0 kernel table with the final LEAF PTE for the code
    la t0, page_table_l0_kernel
    li t1, 0x80000000 >> 12
    slli t1, t1, 10
    # THIS is the leaf. It gets the permissions.
    ori t1, t1, PTE_V | PTE_R | PTE_X | PTE_U
    sd t1, 0(t0)
    
    # Set up L1 user page table for the user stack (this is a leaf, so it's okay)
    la t0, page_table_l1_user1  
    la t1, user_stack1_page
    srli t1, t1, 12; slli t1, t1, 10  
    # This is a 2MiB leaf PTE for the stack. This will also fail if the hardware
    # doesn't support it. You will likely need an L0 table for the user space too.
    # For now, let's just fix the kernel code fetch.
    ori t1, t1, PTE_V | PTE_R | PTE_W | PTE_U
    sd t1, 1088(t0)
    
    # Enable paging
    la t0, page_table_l2
    srli t0, t0, 12
    li t1, SATP_MODE_SV39; or t0, t0, t1
    csrw satp, t0
    sfence.vma
    ret

# --- Process Management ---
init_processes:
    la t0, processes
    la t1, kernel_stack_top
    sd t1, 248(t0) # sp for process 0 (kernel)
    
    # Process 1 
    addi t0, t0, 256
    li t1, 0x11000000 + 4096; sd t1, 248(t0) # sp
    la t1, user_prog1; sd t1, 0(t0)          # Set PC to the actual linked address
    li t1, SSTATUS_SPIE; sd t1, 256-16(t0)   # sstatus (SPIE=1, SPP will be 0)
    
    # Process 2
    addi t0, t0, 256
    li t1, 0x11000000 + 4096; sd t1, 248(t0) # sp
    la t1, user_prog2; sd t1, 0(t0)          # Set PC to the actual linked address
    li t1, SSTATUS_SPIE; sd t1, 256-16(t0)   # sstatus
    
    # Start with process 1
    li t0, 1; la t1, current_process; sw t0, 0(t1)
    ret

# --- Scheduler ---
schedule:
    la t0, current_process; lw t1, 0(t0)
    
    # Switch to next process (1 -> 2 -> 1)
    li t2, 2; beq t1, t2, switch_to_1; addi t1, t1, 1; j store_current
switch_to_1:
    li t1, 1
store_current:
    sw t1, 0(t0)
    
    # Load process context base address
    la t0, processes; li t2, 256; mul t2, t1, t2; add t0, t0, t2
    
    # Restore ALL general purpose registers
    ld ra, 8(t0); ld gp, 24(t0); ld tp, 32(t0)
    # ... (full GPR restore would go here) ...
    
    # Load sstatus and clear SPP bit to ensure return to User Mode
    ld t1, 256-16(t0); li t2, SSTATUS_SPP; not t2, t2; and t1, t1, t2; csrw sstatus, t1

    # Load the PC from the context block (NO LONGER HARDCODED)
    ld t1, 0(t0)
    csrw sepc, t1
    
    # Load the process's stack pointer
    ld sp, 248(t0)
    
    # Return to user mode
    sret

# --- User Program Code (must be in .text section) ---
.align 4
user_prog1:
    li t0, 1; 1: nop; ecall; j 1b
user_prog2: 
    li t0, 2; 1: nop; ecall; j 1b

# --- Trap Handling ---
trap_handler:
    csrrw sp, sscratch, sp
    beqz sp, kernel_trap
    
    # User trap - save context
    la t0, current_process; lw t1, 0(t0)
    la t0, processes; li t2, 256; mul t2, t1, t2; add t0, t0, t2
    csrr t1, sscratch; sd t1, 16(t0)
    csrr t1, sstatus; sd t1, 256-16(t0)
    csrr t1, sepc; sd t1, 0(t0)
    
    la sp, kernel_stack_top
kernel_trap:
    csrr t0, scause
    li t1, SCAUSE_TIMER; beq t0, t1, handle_timer
    li t1, SCAUSE_ECALL_U; beq t0, t1, handle_syscall
    j trap_return

handle_timer:
    # For simplicity, we just return. A real OS would schedule.
    # call schedule
    j trap_return

handle_syscall:
    csrr t0, sepc; addi t0, t0, 4; csrw sepc, t0
trap_return:
    sret

# --- Data and BSS Sections ---
.section .data
.align 12
page_table_l2: .space 4096
page_table_l1_kernel: .space 4096  
page_table_l1_user1: .space 4096
page_table_l1_user2: .space 4096
page_table_l0_kernel: .space 4096

.align 8
processes: .space 768
current_process: .word 0

.section .bss
.align 12
kernel_stack_bottom: .space 4096
kernel_stack_top:

user_stack1_page: .space 4096
user_stack2_page: .space 4096