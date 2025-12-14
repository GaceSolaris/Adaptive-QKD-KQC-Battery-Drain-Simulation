import simpy
import random
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- 1. CONFIGURATION PARAMETERS (Derived from Research) ---
DURATION_24H = 24 * 60 * 60 # 24 Hours
DURATION_1WK = 7 * 24 * 60 * 60 # 1 Week
DURATION_30D = 30 * 24 * 60 * 60 # 30 Days
DURATION_1YR = 365 * 24 * 60 * 60 # 1 Year

# Time is in seconds
SIM_DURATION = DURATION_30D  # Change this to select simulation duration
BATTERY_CAPACITY = 25000.0   # Joules (approx 2000mAh @ 3.7V)
CRITICAL_BATTERY_PCT = 0.30  # 20% Threshold

# Power Consumption Constants
POWER_QKD_ACTIVE = 2.5       # Watts [1]
POWER_QKD_IDLE = 0.4         # Watts 
ENERGY_PQC_OP = 0.0035       # Joules per handshake (3.5mJ) 
ENERGY_AES_OP = 0.00005      # Joules per handshake (Hardware AES)

# Key Buffer (The "Entropy Battery")
BUFFER_MAX_SIZE = 1000       # Max keys stored
KEY_CONSUMPTION_RATE = 1     # Keys needed per minute (avg)

# --- 2. THE SIMULATION MODEL ---

# ==========================================
# CONFIGURATION SWITCH
# ==========================================
# Options: "HYBRID", "QKD_ONLY", "PQC_ONLY"
SIMULATION_TYPE = "PQC_ONLY"

class EdgeNode:
    def __init__(self, env):
        self.env = env
        self.battery = simpy.Container(env, init=BATTERY_CAPACITY, capacity=BATTERY_CAPACITY)
        self.key_buffer = simpy.Container(env, init=50, capacity=BUFFER_MAX_SIZE)
        self.mode = "INIT"
        self.qber = 0.01  # Initial Quantum Bit Error Rate (1%)
        
        # Metrics for Analysis
        self.history_time = []
        self.history_battery = []
        self.history_buffer = []
        self.history_mode = []

        # Start Processes
        self.env.process(self.security_controller())
        self.env.process(self.data_transmission_process())
        self.env.process(self.battery_drain_process())

    def security_controller(self):
        """
        Master Logic capable of running all 3 experimental modes.
        """
        while True:
            battery_pct = self.battery.level / self.battery.capacity
            
            # --- MODE A: PQC ONLY (Software Baseline) ---
            if SIMULATION_TYPE == "PQC_ONLY":
                # Never turns on QKD lasers. Relies 100% on Math.
                # Very low power, but theoretically vulnerable to future mathematical breaks.
                self.mode = "PQC_ONLY" 

            # --- MODE B: QKD ONLY (The 'Naive' Control Group) ---
            elif SIMULATION_TYPE == "QKD_ONLY":
                # Ignores battery health. Always tries to fill buffer with Physics.
                # Vulnerable to energy exhaustion.
                if self.qber < 0.05:
                    self.mode = "QKD_ACTIVE"
                else:
                    self.mode = "QKD_IDLE"

            # --- MODE C: HYBRID ADAPTIVE (The Proposed Solution) ---
            elif SIMULATION_TYPE == "HYBRID":
                if battery_pct > 0.50:
                    if self.qber < 0.05:
                        self.mode = "QKD_ACTIVE" # Harvest entropy
                    else:
                        self.mode = "PQC_ONLY"   # Link noisy/attacked
                elif battery_pct > 0.20:
                    if self.key_buffer.level < 100 and self.qber < 0.05:
                        self.mode = "QKD_ACTIVE"
                    else:
                        self.mode = "QKD_IDLE"
                else:
                    self.mode = "CRITICAL_FALLBACK" # Preservation mode

            # Log Data
            self.history_time.append(self.env.now / 3600)
            self.history_battery.append(battery_pct * 100)
            self.history_buffer.append(self.key_buffer.level)
            self.history_mode.append(self.mode_to_int(self.mode))
            
            yield self.env.timeout(60) # Loop every minute

    def battery_drain_process(self):
        """Calculates energy cost based on the active mode."""
        while True:
            drain = 0.0
            
            if self.mode == "QKD_ACTIVE":
                drain = 2.5 # Watts (High Power Laser/Detector)
                if self.key_buffer.level < self.key_buffer.capacity:
                    yield self.key_buffer.put(5)
            
            elif self.mode == "QKD_IDLE":
                drain = 0.4 # Watts (Standby Electronics)
                
            elif self.mode == "PQC_ONLY":
                # MCU Active Power (approx 10-20mW)
                # Note: This is 100x less than QKD Active
                drain = 0.020 
                # PQC keys are generated "on demand" in data_transmission_process, 
                # so we don't fill the buffer here.
                
            elif self.mode == "CRITICAL_FALLBACK":
                drain = 0.005 # Deep Sleep
            
            # Apply drain
            if self.battery.level > drain:
                yield self.battery.get(drain)
            else:
                break # Node Death
                
            yield self.env.timeout(1)

    def data_transmission_process(self):
        """Simulates application consuming keys."""
        while True:
            # Poisson arrival for data transmission
            yield self.env.timeout(random.expovariate(1.0 / 60)) 
            
            if self.mode == "PQC_ONLY":
                # Consumes Energy (CPU), no Buffer use
                if self.battery.level > ENERGY_PQC_OP:
                    yield self.battery.get(ENERGY_PQC_OP)
            else:
                # Consumes Buffer Key + Small AES Energy
                if self.key_buffer.level > 0:
                    yield self.key_buffer.get(1)
                    if self.battery.level > ENERGY_AES_OP:
                        yield self.battery.get(ENERGY_AES_OP)
                else:
                    # Buffer Empty in Critical Mode = SECURITY FAILURE
                    pass 

    def mode_to_int(self, mode):
        mapping = {"QKD_ACTIVE": 3, "QKD_IDLE": 2, "PQC_ONLY": 1, "CRITICAL_FALLBACK": 0}
        return mapping.get(mode, 0)

# --- 3. THREAT SIMULATOR ---
def threat_injector(env, node):
    """Simulates an attacker interfering with the quantum channel."""
    while True:
        # Normal Conditions
        node.qber = random.uniform(0.005, 0.015) 
        yield env.timeout(random.uniform(3600, 10800)) # 1-3 hours
        
        # ATTACK! (Spike QBER)
        print(f"*** ATTACK STARTED at Hour {env.now/3600:.1f} ***")
        node.qber = random.uniform(0.06, 0.12) # >5% triggers High Threat
        yield env.timeout(random.uniform(600, 1800))   # Attack lasts 10-30 mins
        print(f"*** ATTACK ENDED at Hour {env.now/3600:.1f} ***")

# --- 4. RUN SIMULATION ---
env = simpy.Environment()
node = EdgeNode(env)
env.process(threat_injector(env, node))
env.run(until=SIM_DURATION)

# --- 5. VISUALIZATION ---
fig, ax1 = plt.subplots(figsize=(10, 6))

ax1.set_xlabel('Time (Hours)')
ax1.set_ylabel('Battery Level (%)', color='tab:blue')
ax1.plot(node.history_time, node.history_battery, color='tab:blue', label='Battery')
ax1.tick_params(axis='y', labelcolor='tab:blue')
ax1.grid(True, alpha=0.3)

ax2 = ax1.twinx()
ax2.set_ylabel('Key Buffer Level', color='tab:green')
ax2.plot(node.history_time, node.history_buffer, color='tab:green', linestyle='--', label='Entropy Buffer')
ax2.tick_params(axis='y', labelcolor='tab:green')

plt.title('Energy-Security Trade-off: Buffered Fallback Simulation')
fig.tight_layout()
plt.show()

# --- 6. EXPORT DATA TO CSV ---

# Create a DataFrame from the simulation history
df = pd.DataFrame({
    'Time_Hours': node.history_time,
    'Battery_Percent': node.history_battery,
    'Buffer_Level': node.history_buffer,
    'Mode': node.history_mode
})

# Save to CSV
filename = "quantum_sim_results_PQC_Only_30days_New.csv"
df.to_csv(filename, index=False)

print(f"Simulation data successfully saved to {filename}")
print(df.head()) # Show the first 5 rows as a preview