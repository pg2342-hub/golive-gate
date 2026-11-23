"""Assert a results.json reached the expected decision, for CI.

    python scripts/expect.py RESULTS DECISION [--show CHECK] [--fails CHECK]

--show prints that check's verdicts (skipping na) with the agent's reply.
--fails also requires that check to have failed on at least one case, so a
no-go for some other reason cannot stand in for the check doing its job.
"""

import argparse
import json
import sys

p = argparse.ArgumentParser()
p.add_argument("results")
p.add_argument("decision", choices=["go", "partial", "no-go"])
p.add_argument("--show")
p.add_argument("--fails")
args = p.parse_args()

data = json.load(open(args.results, encoding="utf-8"))
ok = True
if data["decision"] != args.decision:
    print(f"{args.results}: expected {args.decision}, got {data['decision']}")
    ok = False

if args.show:
    print(f"judge cost USD: {data['summary']['total_judge_cost_usd']}")
    for case in data["cases"]:
        for run in case["runs"]:
            v = run["verdicts"].get(args.show)
            if v and v["result"] != "na":
                reply = run["output"].get("reply", "") if isinstance(run["output"], dict) else run["output"]
                print(f"{case['id']} {v['result'].upper()}: {v['reason']} | reply: {reply}")

if args.fails:
    failed = [
        c["id"] for c in data["cases"] for r in c["runs"] if r["verdicts"].get(args.fails, {}).get("result") == "fail"
    ]
    if not failed:
        print(f"{args.results}: expected {args.fails} to fail on some case, it never did")
        ok = False
    else:
        print(f"{args.fails} failed on: {', '.join(sorted(set(failed)))}")

print(f"{args.results}: {data['decision']}" + ("" if ok else " (unexpected)"))
sys.exit(0 if ok else 1)
