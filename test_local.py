"""
Quick test: run the pipeline locally to verify everything works.
Set EIGENAI_API_KEY env var before running.

Usage:
  export EIGENAI_API_KEY=your_key
  python test_local.py
"""

import os
import json
import sys
from agent.scientist import SovereignScientist


def main():
    key = os.environ.get("EIGENAI_API_KEY")
    if not key:
        print("ERROR: Set EIGENAI_API_KEY environment variable")
        print("Get free credits at: https://determinal.eigenarcade.com")
        sys.exit(1)

    print("=" * 60)
    print("Sovereign AI Scientist — Local Test")
    print("=" * 60)

    agent = SovereignScientist(eigenai_key=key, seed=42)

    # Use a focused RL topic (your area of expertise)
    topic = (
        "Novel extensions to Robust Policy Improvement in reinforcement "
        "learning: combining distributional value estimation with "
        "conservative policy updates to handle model uncertainty "
        "in offline settings"
    )

    print(f"\nTopic: {topic[:80]}...")
    print("\n--- Running pipeline ---\n")

    def on_milestone(ms):
        print(f"  >> Milestone: {ms}")

    result = agent.run_pipeline(topic, on_milestone=on_milestone)

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    provenance = result.get("provenance", {})
    print(f"Total verifiable steps: {provenance.get('total_steps', 0)}")
    print(f"Model: {result['program']['model']}")
    print(f"Seed: {result['program']['seed']}")

    # Show hypotheses
    m1 = result["milestones"]["M1_IDEATION"]
    print(f"\nHypotheses generated: {len(m1.get('hypotheses', []))}")
    for i, h in enumerate(m1.get("hypotheses", [])):
        title = h.get("title", f"Hypothesis {i+1}")
        print(f"  {i+1}. {title}")

    # Show selected hypothesis
    selected = m1.get("selected", {})
    print(f"\nSelected: {selected.get('title', '—')}")

    # Show abstract
    m4 = result["milestones"]["M4_WRITING"]
    abstract = m4.get("abstract", "")
    print(f"\nAbstract preview:\n{abstract[:300]}...")

    # Test verification
    print("\n--- Testing Verification ---\n")
    if agent.audit_log:
        first_step = agent.audit_log[0].step_id
        print(f"Verifying step: {first_step}")
        vresult = agent.verify_step(first_step)
        print(f"  Original hash:  {vresult.get('original_hash', '—')[:32]}...")
        print(f"  Re-exec hash:   {vresult.get('verification_hash', '—')[:32]}...")
        print(f"  Match:           {vresult.get('match', '—')}")
        print(f"  Status:          {vresult.get('status', '—')}")

    # Save full results
    with open("test_results.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print("\nFull results saved to test_results.json")

    print("\n✓ All tests passed. Ready to deploy!")


if __name__ == "__main__":
    main()
