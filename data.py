# data.py
RESUME_DATA = {
    "master_skills": {
        "Languages": ["C++", "Rust", "Python", "JavaScript", "TypeScript", "VHDL", "MATLAB", "SQL"],
        "Frameworks & Tools": ["React", "React Native", "Node.js", "Firebase", "Git", "Linux (Arch)"],
        "Hardware & Electronics": ["ESP32", "Arduino", "FPGA (Basys 3)", "PCB Design", "RTL-SDR", "Multimeters", "Soldering/Crimping", "3D Printing", "High Voltage Safety"],
        "Engineering Software": ["Vivado", "ModelSim", "Fusion 360"]
    },
    "projects": [
        {
            "id": "aquaflora",
            "title": "AquaFlora Mobile App",
            "tech": "React Native, Firebase, Google Gemini API, Python, TS",
            "date": "Jul. 2023 - Present",
            "master_facts": """
                - Developed a cross-platform mobile app for aquarium management from scratch.
                - Built a Python web scraper to pull, clean, and verify a database of over 650 freshwater fish species.
                - Integrated Google Gemini AI for image recognition so users can take a picture of their tank to identify fish, plants, or detect diseases.
                - Fine-tuned a chatbot using the Gemini API to provide specific aquarium care guidance.
                - Used React Native for the frontend and Firebase for user auth and database.
                - Implemented a monetization strategy with monthly subscriptions.
                - Integrated Google Calendar API for intuitive water-change reminders.
                - Actually marketed the app with zero budget and successfully acquired paying users, proving real-world product-market fit.
                - Built a website using gatsby in order to advertise and get people to sign up for my mailing list.
                - Entered the Google Gemini AI contest.
                - I designed and built a pipeline for people signing up to getting emails to funnel them into downloading the app.
            """,
            "tags": ["software", "ai", "mobile", "fullstack", "product"]
        },
        {
            "id": "steam_deck",
            "title": "Steam Deck Dual Screen Prototype",
            "tech": "CAD, 3D Printing, Hardware Prototyping",
            "date": "Jan 2022 - Mar 2022",
            "master_facts": """
                - Designed and prototyped a custom dual-screen/phone mount for the Valve Steam Deck.
                - Modeled the physical attachments in CAD and 3D printed the iterations to ensure a perfect snap-fit.
                - Sourced components and evolved the design from a simple phone mount to a proprietary screen that connects directly to the system.
                - Validated the product by setting up an Etsy shop and selling ~20 units at $60 each.
                - Handled all manufacturing, quality control, and shipping myself.
            """,
            "tags": ["hardware", "cad", "product", "business"]
        },
        {
            "id": "urepair",
            "title": "URepair Web Platform",
            "tech": "C++, React, Node.js",
            "date": "Oct. 2024 - Dec. 2024",
            "master_facts": """
                - Developed a web-based platform connecting contractors to job opportunities.
                - Worked in a 3-person agile team using Git for version control.
                - Wrote the high-performance backend logic in C++ and the frontend interface in React/Node.js.
                - Specifically implemented and tested 3 different sorting algorithms and 3 data structures to handle job matching.
                - Optimized the search algorithms, improving query response times by over 60%.
            """,
            "tags": ["software", "web", "algorithms", "cpp"]
        },
        {
            "id": "fpga_calculator",
            "title": "FPGA Calculator",
            "tech": "VHDL, Vivado, ModelSim, Basys 3 FPGA",
            "date": "Nov. 2024",
            "master_facts": """
                - Built a four-function hardware calculator on a Basys 3 FPGA.
                - Interfaced the FPGA with a 4-digit 7-segment display and a PMOD KYPD matrix keypad.
                - Implemented addition, subtraction, multiplication, and division using behavioral modeling in VHDL.
                - Handled hardware debouncing for the keypad inputs and multiplexing for the 7-segment display.
                - Partner project for CENG 3010 Digital Systems Design at TRU.
            """,
            "tags": ["hardware", "fpga", "vhdl", "electrical"]
        },
        {
            "id": "universe",
            "title": "Quantum Time Wave Universe Simunation",
            "tech": "Rust",
            "date": "Apr. 2025 - Present",
            "master_facts": """
                - I had a theory that time could be a wave and decided I could potentially prove it or at least make something cool by programming this theory into a simulation.
                - I created a grid of 'planck nodes' that emit time waves at a frequency of planck time and wavelength of planck length.
                - The idea is heavy object stretch time waves to the point where their frequency is 0hz thus stopping time, and if you travel at the speed of light it does the same thus stopping time.
                - I managed to get a 2d simulation working by using a laplacian to spread out theta phase shift.
                - I have since moved from theta phase shift to 2 vectors u/v, to now 3 vectors u/v/w.
                - Rendering to a window with color based on theta where theta is based on u/v, and brightness is based on w aka how much the vectors point towards the camera (outside of the plane.)
                - Added vacuum decay to bring w back towards -1 (vacuum).
                - Added skyrme force to allow stable skyrmions (protons).
                - Stable skyrmions acheived.
                - Added momentum and pushing functions to watch skyrmion interactions.
                - Pushing 2 anti skyrmions together gently joins them together to form what I call anti-helium.
            """,
            "tags": ["software", "rust", "graphics", "math", "performance", "physics"]
        },
        {
            "id": "ray_tracer",
            "title": "Ray Tracing Engine",
            "tech": "Rust, C++",
            "date": "Feb. 2025 - Apr. 2025",
            "master_facts": """
                - Built a 3D ray tracer completely from scratch without using graphics APIs like OpenGL.
                - Implemented core graphics math: rays, materials, primitives, and matrix transforms using OOP abstractions.
                - Optimized runtime performance by 300% by implementing a Bounding Volume Hierarchy (BVH) to reduce intersection checks.
                - Parallelized the rendering workload using multithreading.
                - Incorporated complex physics equations into the graphics engine to simulate gravitational lensing (light bending around a black hole).
            """,
            "tags": ["software", "cpp", "graphics", "math", "performance"]
        },
        {
            "id": "fertilizer",
            "title": "Smart Fertilizer Doser",
            "tech": "ESP32, C++, 3D Printing, PCB Design, Python",
            "date": "Nov. 2024 - Present",
            "master_facts": """
                - Designed and fabricated a custom PCB for a smart aquarium fertilizer doser.
                - Integrated peristaltic pump drivers and capacitive fluid level sensors.
                - Developing ESP32 firmware in C++ to handle dosing schedules across 4 distinct pump channels.
                - Designed a robust C++ state machine to handle dosing sequences, safety checks, and error handling so it doesn't overdose the tank.
                - Built an internal chemical dosage calculator that computes required pump runtimes based on tank volume and solution concentration.
                - Implemented Wi-Fi connectivity to interface with a mobile app.
            """,
            "tags": ["hardware", "embedded", "cpp", "pcb", "iot"]
        },
        {
            "id": "ebike",
            "title": "Modified E-Bike Battery",
            "tech": "Electrical Engineering, Battery Systems",
            "date": "Ongoing",
            "master_facts": """
                - Upgraded a 60v 130A Surron/e-bike battery to handle a continuous output of 180A.
                - Increased overall bike performance from 8kW to 11kW purely by optimizing motor and battery electrical efficiency.
                - Avoided using pre-made kits; designed, soldered, and crimped custom 6 AWG heavy-duty wiring harnesses myself.
                - Reverse-engineered the old data connectors using a multimeter so I wouldn't have to rebuild the entire bike's data loom.
                - Managed high-current electrical safety and heat dissipation.
            """,
            "tags": ["hardware", "electrical", "power", "automotive"]
        },
        {
            "id": "rf_antenna",
            "title": "Custom RF Antenna Tracker",
            "tech": "RTL-SDR, J-Pole, Python",
            "date": "Early 2026",
            "master_facts": """
                - Built and tuned a physical J-pole antenna for specific radio frequency monitoring.
                - Developing a handheld tracking device using a Raspberry Pi Zero and RTL-SDR.
                - Writing Python scripts to perform TDOA (Time Difference of Arrival) multilateration.
                - Capable of locating a signal transmitter physically within an 11-meter accuracy radius.
                - Implemented logic to compare local transmission times with repeater transmission times to drastically increase TDOA precision.
            """,
            "tags": ["hardware", "sdr", "radio", "python", "signals"]
        },
        {
            "id": "vr_gloves",
            "title": "VR Force Feedback Gloves",
            "tech": "ESP32, Potentiometers, Servo Motors",
            "date": "Oct. 2024 - Dec. 2024",
            "master_facts": """
                - Assembled a force-feedback, hand-tracking glove for Virtual Reality.
                - Used potentiometers attached to retractable badge reels to precisely calculate finger bending percentages in real-time.
                - Wired and programmed high-torque servo motors to physically lock the user's fingers when an object intersection is detected in the VR game engine, simulating physical touch.
                - Utilized an ESP32 for low-latency Wi-Fi connectivity to the PC.
                - Gained deep experience in bridging the gap between physical hardware sensors and high-level 3D software engines.
            """,
            "tags": ["hardware", "embedded", "vr", "robotics"]
        }
    ],
    "experience": [
        {
            "company": "Thompson Rivers University",
            "role": "Robotics Research Assistant",
            "dates": "May 2024 -- Jun. 2024",
            "master_facts": """
                - Modeled and verified kinematic equations for mimicking human gait using Python/MATLAB.
                - Validated mathematical functions with 100+ test cases using test-driven development.
                - Used gitlab to show progress and get advice from professor.
                - Had weekly progress meetings to discuss with the other student and the professor in order to better understand the goals as well as what the other was doing.
            """,
            "tags": ["hardware", "software", "robotics"]
        },
        {
            "company": "F\\&M Installations Ltd.",
            "role": "Electrical Apprentice",
            "dates": "Jun. 2025 -- Present",
            "master_facts": """
                - Assisted in substation capacitor bank upgrades, installing 20km of control wiring per week at BC Hydro Kennedy Substation.
                - Upgraded substation guard rails, extended cap bank platforms, installed control wiring to new control building, upgraded all bus bar.
                - Did firestopping around the dam and power house at every electrical penetration using rockwool firestop bricks and red caulk.
                - Demob around site c, getting it ready to hand off to BC Hydro.
            """,
            "tags": ["electrical", "hands_on"]
        }
    ]
}
