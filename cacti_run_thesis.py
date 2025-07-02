from zigzag.cacti.cacti_parser import CactiParser

# --- 1. Define the parameters for the SRAM cache you want to model ---

# Name for identification in logs
memory_name = "sram_512KB"

# Memory type for CACTI
memory_type = "sram"

# Technology node in micrometers (um)
tech_node = 0.028  # 28nm

# Total size in bits
size_in_bits = 512 * 1024 * 8  # 512 KB

# Read and Write bandwidth in bits per cycle
bandwidth = 512

# Port configuration
read_ports = 1
write_ports = 1
read_write_ports = 0  # Use separate read and write ports

# Number of banks the memory is divided into
banks = 1

# --- 2. Instantiate the parser and get the costs ---
try:
    # Create an instance of the CactiParser
    cacti_parser = CactiParser()

    # Call the get_item method with the defined parameters
    read_cost_pj, write_cost_pj, area_mm2 = cacti_parser.get_item(
        mem_name=memory_name,
        mem_type=memory_type,
        size=size_in_bits,
        r_bw=bandwidth,
        r_port=read_ports,
        w_port=write_ports,
        rw_port=read_write_ports,
        bank=banks,
        technology=tech_node,
    )

    # --- 3. Print the results ---
    print("\n" + "=" * 30)
    print("CACTI Simulation Results")
    print("=" * 30)
    print(f"Memory: {memory_name}")
    print(f"  - Area: {area_mm2:.4f} mm^2")
    print(f"  - Read Energy Cost: {read_cost_pj:.4f} pJ per access")
    print(f"  - Write Energy Cost: {write_cost_pj:.4f} pJ per access")
    print("=" * 30)

except (FileNotFoundError, ChildProcessError, ModuleNotFoundError) as e:
    print(f"\nAn error occurred: {e}")
    print("Please ensure that:")
    print("1. You have run 'pip install PyYAML'.")
    print("2. The path to your CACTI installation inside the CactiParser class is correct.")
    print("3. CACTI can be executed correctly from the command line.")
