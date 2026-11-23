"""Draw the verification sample BEFORE checking anything: 2 apps per category, seeded, so it can't be cherry-picked.
A second, disjoint holdout sample (1 per category) is drawn with a different seed and only checked after fixes."""
import csv, random, json
rows = [r for r in csv.reader(open("data/pass1_closed_book.tsv"), delimiter="\t") if r and not r[0].startswith("#") and r[0] != "id"]
ids = [int(r[0]) for r in rows]
cats = {c: [i for i in ids if (i - 1) // 10 == c] for c in range(10)}
rng = random.Random(20261123)            # seed = submission date
sample = sorted(i for c in range(10) for i in rng.sample(cats[c], 2))
rng2 = random.Random(9)                  # holdout seed
holdout = sorted(rng2.choice([i for i in cats[c] if i not in sample]) for c in range(10))
json.dump({"sample_round1": sample, "holdout_round2": holdout, "seeds": [20261123, 9]}, open("data/samples.json", "w"), indent=1)
name = {int(r[0]): r[1] for r in rows}
print("round1:", [(i, name[i]) for i in sample])
print("holdout:", [(i, name[i]) for i in holdout])
