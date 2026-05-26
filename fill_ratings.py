#!/usr/bin/env python3
"""Fill in ratings for newsletter and first 20 journal posts in post-audit.csv."""

import csv

# slug -> (originality, imagery, depth, structure, sentences, voice, pm_share, audience, relevance, action, notes)
RATINGS = {
    # Newsletter (all Public, all PM-shareable)
    "the-lens-edition-1-what-is-product-management": (6, 5, 5, 7, 7, 7, "Y", "P", 4, "Keep", "Good intro; InVideo support example is concrete"),
    "the-lens-edition-2-solving-ambiguous-problems-metrics": (7, 6, 7, 7, 7, 7, "Y", "P", 5, "Keep", "Context-as-leverage quote is memorable"),
    "the-lens-edition-3-pm-leadership-personal-vision-ephemeral-content": (6, 5, 7, 6, 7, 7, "Y", "P", 3, "Revise", "Fleets section is dated (Twitter deprecated Fleets in 2021)"),
    "the-lens-edition-4-compassionate-leadership-strategy": (8, 8, 8, 7, 8, 8, "Y", "P", 5, "Keep", "Grinch/Colonel story are memorable; Porter definition well applied"),
    "the-lens-edition-5-okrs": (6, 5, 7, 8, 8, 7, "Y", "P", 5, "Keep", "Cleanest structure in the series; output vs outcome distinction is sharp"),
    "the-lens-edition-6-books-i-read-in-2020": (5, 4, 4, 6, 7, 8, "Y", "P", 4, "Keep", "Most personal and authentic edition; still useful as a reading list"),
    "the-lens-edition-7-how-to-do-product-prioritization": (7, 7, 8, 8, 8, 7, "Y", "P", 5, "Keep", "Funny Girl and Netflix examples make abstract concepts concrete; best PM piece"),
    "the-lens-edition-8-knowing-your-users-types-of-pms": (7, 7, 7, 7, 7, 7, "Y", "P", 5, "Keep", "Starbucks Strategy / one-person focus tip is actionable"),
    "the-lens-edition-9-preventing-problems-tiers-of-engagement": (8, 6, 8, 7, 8, 7, "Y", "P", 5, "Keep", "Preventable Problem Paradox is a strong original concept"),
    "the-lens-edition-10-risk-reduction-working-with-engineering": (7, 6, 8, 8, 8, 8, "Y", "P", 5, "Keep", "Engineers as partners framing; download-your-brain metaphor is vivid"),
    "the-lens-edition-11-positioning": (8, 9, 7, 8, 8, 8, "Y", "P", 5, "Keep", "Best imagery in the series; Hot Cheetos + KitKat + muffin-vs-cake examples are excellent"),

    # Journal — 20 oldest posts (2004-2005, personal life in Bangalore)
    "trap-trip-report-and-analysis-pondicherry": (5, 5, 4, 4, 5, 7, "N", "F", 2, "Archive", "Personal trip report; warm voice but rough prose and encoding issues"),
    "ombattu-gudda": (5, 5, 4, 4, 5, 7, "N", "F", 2, "Archive", "Trek narrative; personal charm, not for public"),
    "yuva": (5, 5, 5, 5, 6, 6, "N", "F", 3, "Archive", "Bollywood review with some film craft observation"),
    "hum-tum": (6, 5, 4, 5, 5, 7, "N", "F", 2, "Archive", "Creative dialogue format shows personality; deeply personal"),
    "rangashankara-rehearsal": (5, 6, 5, 6, 6, 6, "N", "F", 2, "Archive", "Theatre visit write-up; decent descriptive writing"),
    "veer-zaara": (5, 5, 5, 5, 6, 6, "N", "F", 2, "Archive", "Film review; formula-driven but competent"),
    "launch": (4, 4, 4, 5, 5, 7, "N", "A", 3, "Archive", "First blog announcement post; historically interesting"),
    "oxymoronica": (5, 5, 6, 5, 5, 6, "N", "F", 3, "Archive", "Book response; shows intellectual curiosity"),
    "munnar-and-ootywhich-comes-on-the-way": (5, 6, 4, 5, 5, 6, "N", "F", 2, "Archive", "Travel log; good detail but personal"),
    "my-daily-happenings": (6, 4, 4, 4, 6, 7, "N", "F", 2, "Archive", "Dry humor piece about routine; charming brevity"),
    "g-simplicity": (5, 4, 5, 4, 5, 6, "N", "F", 3, "Archive", "Early Google take; dated but shows product thinking emerging"),
    "oo-aa-ouch": (3, 3, 2, 3, 4, 5, "N", "A", 1, "Archive", "One-liner about sprained leg; no substance"),
    "rangashankara-the-final-rehearsal": (5, 6, 5, 5, 6, 6, "N", "F", 2, "Archive", "Theatre review; better than the first rehearsal post"),
    "on-my-way-beat": (7, 6, 5, 7, 6, 7, "N", "F", 3, "Archive", "Best writing in this batch — stream-of-consciousness rhythm works"),
    "what-do-i-do": (5, 4, 4, 5, 5, 6, "N", "A", 2, "Archive", "Overwhelm list; personal, no public value"),
    "club-experience": (5, 5, 4, 5, 5, 6, "N", "F", 2, "Archive", "Friend's club visit told second-hand; light"),
    "packed-weekend": (4, 4, 4, 4, 5, 6, "N", "A", 2, "Archive", "Weekend recap; thin content"),
    "see-me": (2, 2, 1, 2, 3, 4, "N", "A", 1, "Delete", "Just a photo placeholder; no content"),
    "blogging": (5, 4, 5, 5, 5, 5, "N", "F", 2, "Archive", "2004 blogging zeitgeist piece; now dated"),
    "desk-top": (4, 4, 3, 3, 5, 6, "N", "A", 1, "Archive", "Desk description; ephemeral slice of life, no lasting value"),
}

rows = []
with open("post-audit.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        slug = row["slug"]
        if slug in RATINGS:
            r = RATINGS[slug]
            row["originality"] = r[0]
            row["imagery"] = r[1]
            row["philosophical_depth"] = r[2]
            row["structure"] = r[3]
            row["sentence_control"] = r[4]
            row["voice"] = r[5]
            row["pm_share"] = r[6]
            row["audience"] = r[7]
            row["relevance"] = r[8]
            row["action"] = r[9]
            row["notes"] = r[10]
        rows.append(row)

with open("post-audit.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

rated = sum(1 for r in rows if r["action"])
print(f"Rated {rated} / {len(rows)} posts")
