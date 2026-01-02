# Chipyard BootROM and Minimal Kernels

Minimal baremetal BootROM and kernel examples written to run on Rocket Chip via Chipyard.
These are intentionally small assembly-only examples for testing, learning, or using as a starting
point for custom boot ROMs and tiny kernels.

Files
- `cs_umode.S` : Performs context switching between two processes in U mode
- `bootrom.S` : Minimal Boot ROM — a small assembly BootROM that sets up machine mode and
  jumps to a kernel image or entry point. Use this as the primary minimal boot ROM.
- `bootrom2.S` : Variant Boot ROM — alternate layout/initialization or experiment with a
  different entry/addressing style.
- `bootrom3.S` : Another Boot ROM variant — additional experimental/minimal variant.
- `hard_kernel.S` : Minimal kernel marked "hard" — small example kernel that demonstrates
  low-level baremetal behavior (e.g., simple loop, memory accesses, or MMIO hits).
- `kernel2.S` : Alternate kernel example — another tiny kernel variant useful for testing
  different startup sequences or peripheral access patterns.
- `slack_kernel.S` : Slack/relaxed kernel example — small kernel used to exercise timing,
  no-OS behavior, or alternate control flow.


Notes
- These files are small, hand-written RISC-V assembly sources intended to be used inside
  a Chipyard/ Rocket Chip boot flow as BootROM or kernel payloads.
- Exact behavior differs per file — inspect the comments at the top of each `.S` file for
  precise entry symbols, expected memory layout, and any included sample data.

Building / Converting to a BootROM image (example)
- Requirements: a RISC-V cross toolchain (GNU binutils / gcc for RISC-V), e.g.:
  `riscv64-unknown-elf-gcc`, `riscv64-unknown-elf-objcopy`, `riscv64-unknown-elf-ld`.
- Minimal example to assemble/link a single `.S` file into a binary then convert to a
  simple hex/binary payload (adjust flags, linker script, and ISA as needed):

```bash
# assemble & link (example, requires a suitable `linker.ld`)
riscv64-unknown-elf-gcc -nostdlib -T linker.ld -march=rv64gc -mabi=lp64d \
  -o kernel.elf bootrom.S

# convert to raw binary
riscv64-unknown-elf-objcopy -O binary kernel.elf kernel.bin

# create a simple 32-bit little-endian hex list (useful for some BootROM generators)
hexdump -v -e '1/4 "%08x\n"' kernel.bin > bootrom.hex
```

- How you include `bootrom.hex` into Chipyard depends on your Chipyard configuration and
  the BootROM packaging you use (Verilator emulation, FPGA image, or a boot ROM generator
  inside your SoC generator). Common patterns:
  - Provide `bootrom.hex` to the BootROM generator used by your Chipyard build.
  - Embed the binary into a ROM section in the system-level memory map.

Tips
- Inspect each `.S` for the defined entry symbol (commonly `_start` or `entry`) and
  any linker script expectations. If you change the link address, update the linker
  script accordingly.
- If you want UART output for debugging, confirm the kernel's MMIO addresses match your
  Rocket Chip MMIO map and that the UART is enabled in your Chipyard configuration.
