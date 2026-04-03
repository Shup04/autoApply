# data.py
RESUME_DATA = {
    "projects": [
        {
            "id": "ebike",
            "title": "Modified E-Bike Battery",
            "tech": "Electrical Engineering, Battery Systems",
            "bullets": [
                "Upgraded 60v 130A e-bike battery to use custom connectors and wiring for higher current output[cite: 124, 125].",
                "Increased performance from 8kW to 11kW by optimizing motor/battery efficiency[cite: 126]."
            ],
            "tags": ["hardware", "electrical", "performance"]
        },
        {
            "id": "rf_antenna",
            "title": "Custom RF Antenna Setup",
            "tech": "RTL-SDR, J-Pole, Python",
            "bullets": [
                "Built and tuned a j-pole antenna for specific radio frequency monitoring[cite: 116].",
                "Developed a handheld device using TDOA (Time Difference of Arrival) multilateration to locate signal transmitters within 11m[cite: 117]."
            ],
            "tags": ["hardware", "sdr", "radio", "python"]
        },
        {
            "id": "vr_gloves",
            "title": "VR Force Feedback Gloves",
            "tech": "Arduino, Potentiometers, Servo Motors",
            "bullets": [
                "Used potentiometers and badge reels to detect finger bending percentage[cite: 121, 122].",
                "Implemented servo motor feedback to physically stop finger movement when object intersection is detected in VR[cite: 122, 123]."
            ],
            "tags": ["hardware", "arduino", "robotics", "vr"]
        },
        # (Add your other projects like Ray Tracing, FPGA Calculator, and Smart Fertilizer Doser here) [cite: 48, 100]
    ],
    "experience": [
        {
            "company": "Thompson Rivers University",
            "role": "Robotics Research Assistant",
            "dates": "May 2024 -- Jun. 2024",
            "bullets": [
                "Modeled and verified kinematic equations for mimicking human gait using Python/MATLAB.",
                "Validated mathematical functions with 100+ test cases using test-driven development."
            ]
        },
        {
            "company": "F\\&M Installations Ltd.", # <-- Fixed ampersand!
            "role": "Electrical Apprentice",
            "dates": "Jun. 2025 -- Present",
            "bullets": [
                "Assisted in substation capacitor bank upgrades, installing 20km of control wiring per week at Site C Dam."
            ]
        }
    ]
}
