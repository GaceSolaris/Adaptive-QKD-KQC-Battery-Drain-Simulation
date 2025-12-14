# Mitigating Battery Exhaustion Attacks via Adaptive Hybrid QKD-PQC Architectures

## Purpose of the Repository

This repository provides a couple of scripts that are used for simulating the effects of battery drain on a QKD-PQC Hybrid Internet of Things (IoT) System. QKD stands for Quantum Key Distribution, and PQC stands for Post-Quantum Cryptography. The specifics of the simulation can be referenced in the provided project paper. 

### quantum_simulation.py
The following script provides a general simulation that runs one of three modes:
1. QKD-Only
2. PQC-Only
3. Hybrid QKD-PQC

Four Time ranges are provided for testing longer cases:
1. 24 Huurs
2. 7 Days (1 Week)
3. 30 Days
4. 1 Year

The purpose of the time durations were for observing trends past time periods where data was cut off.

Factors like attacker type, drainage consumption, and other factors can be modified to simulate existing devices.

### battery_exhaustion_sim.py
The following script aims to simulate a type of "Quantum Vampire" Attack on a QKD-Only IoT device and a Adaptable Hybrid QKD-PQC IoT device. The 'Quantum Vampire" attack focuses on forcing a device to repeatable continue to drain battery life generating keys, and showcases the potential lowering battery drain with an adaptable hybrid system.
