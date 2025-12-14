import simpy
import random
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# 1. EXPERIMENTAL CONFIGURATION
# ==========================================

# Simulation Duration options (in seconds)
DURATION_24H = 24 * 60 * 60
DURATION_1WK = 7 * 24 * 60 * 60
DURATION_30D = 30 * 24 * 60 * 60
DURATION_1YR = 365 * 24 * 60 * 60

# Select your duration here:
CURRENT_DURATION = DURATION_1YR

# Hardware Energy Profiles (Derived from Research)
# Battery: 3000mAh @ 3.7V = ~11.1 Wh = ~40,000 Joules
BATTERY_CAPACITY_J = 40000.0 

# Power Consumption (Watts = Joules/sec)
# QKD Device (Active Laser/Detector + Cooling)
P_QKD_ACTIVE = 2.50   #
P_QKD_IDLE   = 0.40   # Standby electronics

# Microcontroller (Cortex-M4) for PQC
P_MCU_ACTIVE = 0.08   # 80mW active processing
P_MCU_SLEEP  = 0.001  # 1mW deep sleep

# Protocol Costs (Time in seconds)
TIME_QKD_HANDSHAKE = 5.0   # Time to sift, correct errors, privacy amplify
TIME_PQC_HANDSHAKE = 0.05  # Kyber-768 encapsulation time (~ms range)

# Attack Parameters
ATTACK_START_TIME = CURRENT_DURATION * 0.20 # Attack starts at 20% mark
ATTACK_INTENSITY  = 0.95 # 95% probability of QKD failure (noise injection)

# ==========================================
# 2. THE SIMULATION MODEL
# ==========================================

class IoTNode:
    def __init__(self, env, node_type, capacity):
        self.env = env
        self.node_type = node_type # "NAIVE" or "ADAPTIVE"
        self.battery = simpy.Container(env, init=capacity, capacity=capacity)
        self.is_alive = True
        
        # State Tracking
        self.state = "SLEEP" # SLEEP, PQC, QKD, DEAD
        self.consecutive_failures = 0
        self.keys_generated = 0
        
        # Data Logging
        self.history = []
        
        # Start core processes
        self.env.process(self.operation_cycle())
        self.env.process(self.monitor())

    def consume_energy(self, watts, duration):
        """Helper to drain battery and check for death"""
        joules = watts * duration
        if self.battery.level > joules:
            self.battery.get(joules)
        else:
            self.battery.get(self.battery.level) # Drain rest
            self.is_alive = False
            self.state = "DEAD"
            
    def operation_cycle(self):
        """The main lifecycle of the device"""
        while self.is_alive:
            # 1. Determine Environmental Threat (Attack Simulation)
            is_under_attack = (self.env.now > ATTACK_START_TIME) and (random.random() < 0.8)
            
            # 2. Attempt Key Generation (Scheduled every 10 mins normally)
            # Under attack, a Naive node might retry immediately
            
            if self.node_type == "NAIVE":
                # Naive Strategy: Always prefer QKD. Retry immediately on failure.
                success = yield from self.attempt_qkd(is_under_attack)
                
                if not success:
                    # Naive Retry Loop (The Vampire Attack Vulnerability)
                    # It stays awake trying to fix the link
                    yield self.env.timeout(1) # Short wait then retry
                else:
                    yield self.env.timeout(600) # Sleep 10 mins if successful

            elif self.node_type == "ADAPTIVE":
                # Hybrid Strategy: Check failures and battery
                battery_pct = self.battery.level / self.battery.capacity
                
                # Decision Logic
                if self.consecutive_failures > 3 or battery_pct < 0.15:
                    # Fallback to PQC (Software)
                    yield from self.perform_pqc()
                    # Backoff: Sleep longer to save battery
                    yield self.env.timeout(3600) # Sleep 1 hour
                else:
                    # Try QKD
                    success = yield from self.attempt_qkd(is_under_attack)
                    if not success:
                        self.consecutive_failures += 1
                        yield self.env.timeout(10) # Wait a bit before retry
                    else:
                        self.consecutive_failures = 0
                        yield self.env.timeout(600) # Normal sleep

    def attempt_qkd(self, is_under_attack):
        """Simulates a QKD handshake attempt"""
        self.state = "QKD_ACTIVE"
        
        # QKD Hardware must spin up and fire lasers (High Power)
        # Even a failed attempt consumes full power for the handshake duration
        yield self.env.timeout(TIME_QKD_HANDSHAKE)
        self.consume_energy(P_QKD_ACTIVE, TIME_QKD_HANDSHAKE)
        
        # Check result
        if is_under_attack and random.random() < ATTACK_INTENSITY:
            # Attack causes High QBER -> Protocol Abort -> No Key
            return False 
        else:
            self.keys_generated += 1
            return True

    def perform_pqc(self):
        """Simulates a Post-Quantum Cryptography handshake"""
        self.state = "PQC_PROCESS"
        
        # MCU wakes up, runs Kyber math, goes back to sleep
        yield self.env.timeout(TIME_PQC_HANDSHAKE)
        self.consume_energy(P_MCU_ACTIVE, TIME_PQC_HANDSHAKE)
        
        # PQC is purely mathematical; noise doesn't stop it (unless link is cut)
        self.keys_generated += 1
        self.consecutive_failures = 0 # Reset failure counter

    def monitor(self):
        """Logs data every simulation hour"""
        while True:
            self.history.append({
                'Time_Day': self.env.now / 86400.0,
                'Battery_J': self.battery.level,
                'Battery_Pct': (self.battery.level / BATTERY_CAPACITY_J) * 100,
                'State': self.state,
                'Keys': self.keys_generated
            })
            
            # Idle Drain during the monitor interval
            if self.is_alive and self.state!= "QKD_ACTIVE":
                # Simplified idle drain for the hour
                # In reality, this happens second-by-second in the cycle
                self.consume_energy(P_MCU_SLEEP + P_QKD_IDLE, 3600) 
            
            if not self.is_alive:
                break
                
            yield self.env.timeout(3600) # Log every hour

# ==========================================
# 3. EXECUTION WRAPPER
# ==========================================

def run_experiment():
    print(f"--- Starting Simulation: {CURRENT_DURATION/86400:.1f} Days ---")
    print(f"--- Attack Scheduled at Day {ATTACK_START_TIME/86400:.1f} ---")

    # Run Scenario A: Naive QKD
    env_naive = simpy.Environment()
    node_naive = IoTNode(env_naive, "NAIVE", BATTERY_CAPACITY_J)
    env_naive.run(until=CURRENT_DURATION)
    df_naive = pd.DataFrame(node_naive.history)
    # df_naive = 'Naive QKD' # Removed incorrect assignment

    # Run Scenario B: Adaptive Hybrid
    env_adapt = simpy.Environment()
    node_adapt = IoTNode(env_adapt, "ADAPTIVE", BATTERY_CAPACITY_J)
    env_adapt.run(until=CURRENT_DURATION)
    df_adapt = pd.DataFrame(node_adapt.history)
    # df_adapt = 'Adaptive Hybrid' # Removed incorrect assignment

    return df_naive, df_adapt

# ==========================================
# 4. PLOTTING & ANALYSIS
# ==========================================

if __name__ == "__main__":
    df_n, df_a = run_experiment()

    # Combine for CSV
    # Add a 'Strategy' column to each DataFrame for identification
    df_n['Strategy'] = 'Naive QKD'
    df_a['Strategy'] = 'Adaptive Hybrid'
    full_data = pd.concat([df_n, df_a])
    full_data.to_csv("battery_exhaustion_attack_results_1Yr.csv", index=False)
    print("Results saved to 'battery_exhaustion_attack_results_1Yr.csv'")

    # Plotting
    plt.figure(figsize=(12, 6))

    # Plot Naive
    plt.plot(df_n['Time_Day'], df_n['Battery_Pct'],
             label='Naive QKD Node', color='red', linestyle='-', linewidth=2)

    # Plot Adaptive
    plt.plot(df_a['Time_Day'], df_a['Battery_Pct'],
             label='Adaptive Hybrid Node', color='green', linestyle='--', linewidth=2)

    # Attack Marker
    plt.axvline(x=ATTACK_START_TIME/86400, color='black', linestyle=':', label='Attack Start')

    plt.title(f'Impact of "Quantum Vampire" Attack on IoT Battery Life\n(Duration: {CURRENT_DURATION/86400:.0f} Days)', fontsize=14)
    plt.xlabel('Simulation Time (Days)', fontsize=12)
    plt.ylabel('Battery State of Charge (%)', fontsize=12)
    plt.ylim(0, 105)
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Add annotation for Death
    # Check for Naive node death
    if df_n['Battery_Pct'].iloc[-1] <= 0:
        # Find the first day the battery percentage dropped to or below 0
        death_day_index = df_n[df_n['Battery_Pct'] <= 0].index[0]
        death_day = df_n.loc[death_day_index, 'Time_Day']
        plt.text(death_day, 5, f' Naive Node Death\n Day {death_day:.1f}', color='red', fontweight='bold', ha='left')

    # Check for Adaptive node death
    if df_a['Battery_Pct'].iloc[-1] <= 0:
        # Find the first day the battery percentage dropped to or below 0
        death_day_index_a = df_a[df_a['Battery_Pct'] <= 0].index[0]
        death_day_a = df_a.loc[death_day_index_a, 'Time_Day']
        plt.text(death_day_a, 10, f' Adaptive Node Death\n Day {death_day_a:.1f}', color='green', fontweight='bold', ha='left')

    plt.tight_layout()
    plt.show()