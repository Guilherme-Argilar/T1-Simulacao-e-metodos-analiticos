import sys
from simulator import Simulator

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "model.yml"
    print(f"Running simulation with '{path}'\n")
    sim = Simulator(path)
    sim.run()
    out = sim.report()
    print(out)
    with open("simulation_result.txt", "w", encoding="utf-8") as f:
        f.write(out)
    print("\nResults saved to 'simulation_result.txt'.")

if __name__ == "__main__":
    main()
