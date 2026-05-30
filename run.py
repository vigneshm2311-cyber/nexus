import sys
import argparse
from nexus.config import ResearchConfig
from nexus.conductor import run
from nexus.output import generate

def parse_args():
    parser = argparse.ArgumentParser(
        description="NEXUS — Multi-agent research intelligence platform"
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="Research goal (wrap in quotes)"
    )
    parser.add_argument(
        "--rounds", type=int, default=None,
        help="Number of research rounds (default: 3)"
    )
    parser.add_argument(
        "--hypotheses", type=int, default=None,
        help="Hypotheses per round (default: 5)"
    )
    parser.add_argument(
        "--papers", type=int, default=None,
        help="Papers per hypothesis (default: 3)"
    )
    parser.add_argument(
        "--backend", type=str, default=None,
        choices=["ollama", "grok"],
        help="LLM backend override"
    )
    return parser.parse_args()

def main():
    args = parse_args()

    if not args.goal:
        print("Usage: python run.py \"your research goal here\"")
        print("       python run.py \"your goal\" --rounds 2 --hypotheses 5")
        sys.exit(1)

    config = ResearchConfig()
    if args.rounds:
        config.max_rounds = args.rounds
    if args.hypotheses:
        config.hypotheses_per_round = args.hypotheses
    if args.papers:
        config.papers_per_hypothesis = args.papers
    if args.backend:
        config.llm_backend = args.backend

    config.validate()

    try:
        result = run(args.goal, config)
        md_path, json_path = generate(result, config)

        print("\n" + "="*50)
        print("NEXUS — TOP HYPOTHESES")
        print("="*50)
        for i, h in enumerate(result["ranked"], 1):
            print(f"\n{i}. [{h['score']:.3f}] {h['hypothesis_text']}")
            print(f"   N={h['novelty']} E={h['evidence']} F={h['feasibility']}")
        print("\n" + "="*50)
        print(f"Full report: {md_path}")
        print(f"JSON export: {json_path}")
        print("="*50 + "\n")

    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[NEXUS] Interrupted by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
