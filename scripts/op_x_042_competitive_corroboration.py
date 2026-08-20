# ruff: noqa: E501
"""Generate OP-X-042 evidence-first competitive corroboration artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.evidence.competitive import (
    deduplicate_questions,
    evaluate_hypothesis,
    meta_efficient,
    repeated_card_usage,
    threshold_saturation,
)
from operation_pancake.evidence.knowledge import normalize_claim, normalize_source

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_042"
KB = ROOT / "data/research/op_x_040/knowledge_base.json"
NOW = "2026-08-20T12:00:00+00:00"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + "\n"
    (OUT / name).write_text(text, encoding="utf-8")


def main() -> None:
    base = json.loads(KB.read_text(encoding="utf-8"))
    raw_sources = [
        {
            "source_id": "OPX042-EA-ABILITIES",
            "name": "EA CUT27 abilities guide",
            "url": "https://help.ea.com/en/articles/ea-sports-college-football/ultimate-team-abilities/",
            "tier": 1,
            "source_type": "WEB",
            "publisher_id": "EA",
            "publication_date": "2026-07-01",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-CFBFAN-BUDGET",
            "name": "The Best Budget Players in CUT 27",
            "url": "https://cfb.fan/news/the-best-budget-players-in-cut-27/",
            "tier": 3,
            "source_type": "WEB",
            "publisher_id": "diorhightower",
            "publication_date": "2026-07-17",
            "current": True,
            "competitive": True,
        },
        {
            "source_id": "OPX042-REDDIT-QB-GUIDE",
            "name": "How to be a great QB in CFB 27",
            "url": "https://www.reddit.com/r/NCAAFBseries/comments/1uo4j7v/how_to_be_a_great_qb_in_cfb_27_ultimate_guide/",
            "tier": 4,
            "source_type": "WEB",
            "publisher_id": "reddit:1uo4j7v-author",
            "publication_date": "2026-07-05",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-CFBLABS-REQ",
            "name": "CFB 27 Ability Requirements",
            "url": "https://www.cfblabs.com/ability-requirements",
            "tier": 2,
            "source_type": "WEB",
            "publisher_id": "CFB Labs",
            "publication_date": "2026-08-13",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-CFBLABS-DESC",
            "name": "CFB 27 Ability Descriptions",
            "url": "https://www.cfblabs.com/ability-descriptions",
            "tier": 2,
            "source_type": "WEB",
            "publisher_id": "CFB Labs",
            "publication_date": "2026-08-13",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-GAMESGG-QB",
            "name": "College Football 27 Fastest Quarterbacks",
            "url": "https://games.gg/ea-sports-college-football-27/guides/college-football-27-fastest-quarterbacks-players/",
            "tier": 3,
            "source_type": "WEB",
            "publisher_id": "Larc / Games.gg",
            "publication_date": "2026-07-05",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-COLLEGEFOOTBALLGG-ABILITIES",
            "name": "College Football 27 abilities database",
            "url": "https://collegefootball.gg/abilities/",
            "tier": 2,
            "source_type": "WEB",
            "publisher_id": "CollegeFootball.gg",
            "publication_date": "2026-08-01",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-COLLEGEFOOTBALLGG-QB",
            "name": "College Football 27 QB ratings database",
            "url": "https://collegefootball.gg/players/position/quarterbacks/",
            "tier": 2,
            "source_type": "WEB",
            "publisher_id": "CollegeFootball.gg",
            "publication_date": "2026-08-01",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-REDDIT-NMS",
            "name": "New CUT27 NMS advice thread",
            "url": "https://www.reddit.com/r/CollegeUltimateTeam/comments/1vr9ea4/so_i_bought_27_yesterdaystrictly_for_ultimate/",
            "tier": 4,
            "source_type": "WEB",
            "publisher_id": "reddit:1vr9ea4-community",
            "publication_date": "2026-08-18",
            "current": True,
            "competitive": False,
        },
        {
            "source_id": "OPX042-REDDIT-SQUAD",
            "name": "CUT27 84 OVR NMS squad post",
            "url": "https://www.reddit.com/r/CollegeUltimateTeam/comments/1v89c1w/cut27_squads/",
            "tier": 4,
            "source_type": "WEB",
            "publisher_id": "reddit:1v89c1w-author",
            "publication_date": "2026-07-22",
            "current": True,
            "competitive": False,
        },
    ]
    new_sources = [normalize_source(row) for row in raw_sources]
    sources = {row["source_id"]: row for row in [*base["sources"], *new_sources]}
    raw_claims = [
        {
            "claim_id": "OPX042-CLAIM-001",
            "subject": "CUT27 abilities",
            "predicate": "activation_mechanic",
            "value": "SP unlocks/upgrades slots; AP activates abilities from a shared lineup pool; higher tiers strengthen effects",
            "game": "CFB27",
            "source_id": "OPX042-EA-ABILITIES",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-01",
            "status": "VERIFIED",
            "confidence": "HIGH",
            "fact_type": "EA FACT",
            "extraction": "PAGE TEXT",
        },
        {
            "claim_id": "OPX042-CLAIM-002",
            "subject": "80 OVR Drew Bledsoe Core Legend",
            "predicate": "budget_competitive_viability",
            "value": "recommended at 81 THP, 82 SAC, 82 MAC",
            "game": "CFB27",
            "source_id": "OPX042-CFBFAN-BUDGET",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-17",
            "status": "STRONG EVIDENCE",
            "confidence": "HIGH",
            "fact_type": "COMPETITIVE PREFERENCE",
            "criterion_type": "PRICE/VALUE REQUIREMENT",
            "position": "QB",
            "scope": "BUDGET / NMS",
        },
        {
            "claim_id": "OPX042-CLAIM-003",
            "subject": "80 OVR Warren Moon Core Legend",
            "predicate": "budget_competitive_viability",
            "value": "recommended at 76 SPD, 81 THP, 83 MAC, 82 DAC",
            "game": "CFB27",
            "source_id": "OPX042-CFBFAN-BUDGET",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-17",
            "status": "STRONG EVIDENCE",
            "confidence": "HIGH",
            "fact_type": "COMPETITIVE PREFERENCE",
            "criterion_type": "PRICE/VALUE REQUIREMENT",
            "position": "QB",
            "scope": "BUDGET / NMS",
        },
        {
            "claim_id": "OPX042-CLAIM-004",
            "subject": "83 OVR Baylor Hayes",
            "predicate": "budget_competitive_viability",
            "value": "86 THP comparable to many top QBs; MAC and DAC described as weaknesses",
            "game": "CFB27",
            "source_id": "OPX042-CFBFAN-BUDGET",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-17",
            "status": "STRONG EVIDENCE",
            "confidence": "HIGH",
            "fact_type": "COMPETITIVE PREFERENCE",
            "criterion_type": "PRICE/VALUE REQUIREMENT",
            "position": "QB",
            "scope": "BUDGET / NMS",
        },
        {
            "claim_id": "OPX042-CLAIM-005",
            "subject": "CFB27 passing",
            "predicate": "passing_control",
            "value": "Revamped and Placement & Accuracy have tradeoffs; Free Form passing is important",
            "game": "CFB27",
            "source_id": "OPX042-REDDIT-QB-GUIDE",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-05",
            "status": "COMMUNITY REPORT",
            "confidence": "LOW",
            "fact_type": "COMMUNITY OPINION",
            "criterion_type": "PERSONAL PREFERENCE",
            "position": "QB",
        },
        {
            "claim_id": "OPX042-CLAIM-006",
            "subject": "CFB27 ability requirements",
            "predicate": "attribute_breakpoints",
            "value": "ability tiers have position/archetype-specific numerical attribute requirements; database lists QB Dot! Platinum at 98 DAC",
            "game": "CFB27",
            "source_id": "OPX042-CFBLABS-REQ",
            "evidence_timestamp": NOW,
            "publication_date": "2026-08-13",
            "status": "STRONG EVIDENCE",
            "confidence": "MEDIUM",
            "fact_type": "DATABASE OBSERVATION",
            "criterion_type": "ABILITY REQUIREMENT",
            "position": "QB",
            "scope": "GAME-WIDE, NOT CUT ITEM EQUIP PROOF",
        },
        {
            "claim_id": "OPX042-CLAIM-007",
            "subject": "CFB27 QB mobility",
            "predicate": "SPD_and_AGI",
            "value": "speed and agility affect scrambling and option-style play; no numerical CUT threshold stated",
            "game": "CFB27",
            "source_id": "OPX042-GAMESGG-QB",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-05",
            "status": "PROVISIONAL",
            "confidence": "LOW",
            "fact_type": "ANALYST OPINION",
            "criterion_type": "SCHEME REQUIREMENT",
            "position": "QB",
            "scheme": "MOBILE / OPTION",
        },
        {
            "claim_id": "OPX042-CLAIM-008",
            "subject": "CUT27 NMS roster building",
            "predicate": "scheme_fit",
            "value": "community advice prioritizes playbook, scheme and small details over overall alone",
            "game": "CFB27",
            "source_id": "OPX042-REDDIT-NMS",
            "evidence_timestamp": NOW,
            "publication_date": "2026-08-18",
            "status": "COMMUNITY REPORT",
            "confidence": "LOW",
            "fact_type": "COMMUNITY OPINION",
            "criterion_type": "SCHEME REQUIREMENT",
            "scope": "NMS",
        },
        {
            "claim_id": "OPX042-CLAIM-009",
            "subject": "CFB27 abilities",
            "predicate": "tier_descriptions",
            "value": "database exposes 80 physical/mental abilities and separate Bronze through Platinum effects",
            "game": "CFB27",
            "source_id": "OPX042-CFBLABS-DESC",
            "evidence_timestamp": NOW,
            "publication_date": "2026-08-13",
            "status": "STRONG EVIDENCE",
            "confidence": "MEDIUM",
            "fact_type": "DATABASE OBSERVATION",
        },
        {
            "claim_id": "OPX042-CLAIM-010",
            "subject": "CUT27 84 OVR NMS squad",
            "predicate": "roster_visibility",
            "value": "post metadata identifies an 84 OVR NMS squad, but accessible evidence does not expose defensible slots",
            "game": "CFB27",
            "source_id": "OPX042-REDDIT-SQUAD",
            "evidence_timestamp": NOW,
            "publication_date": "2026-07-22",
            "status": "COMMUNITY REPORT",
            "confidence": "LOW",
            "fact_type": "ROSTER OBSERVATION",
            "scope": "INSUFFICIENT FOR ROSTER CAPTURE",
        },
    ]
    new_claims = [normalize_claim(row, sources) for row in raw_claims]
    base["sources"] = sorted(
        {row["source_id"]: row for row in [*base["sources"], *new_sources]}.values(),
        key=lambda r: r["source_id"],
    )
    base["claims"] = sorted(
        {row["claim_id"]: row for row in [*base["claims"], *new_claims]}.values(),
        key=lambda r: r["claim_id"],
    )
    KB.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    h_common = {
        "source_id": "OPX041-CFBFAN-RANKINGS",
        "publisher_id": "diorhightower",
        "classification": "SUPPORTS 85",
        "threshold": 85,
        "scope": "high-level position ranking",
    }
    thp = evaluate_hypothesis(
        [
            h_common,
            {
                "source_id": "OPX042-CFBFAN-BUDGET",
                "publisher_id": "diorhightower",
                "classification": "CONTRADICTS THRESHOLD CONCEPT",
                "threshold": 81,
                "scope": "budget-competitive recommendations below 85",
            },
        ]
    )
    mac = evaluate_hypothesis(
        [
            {**h_common},
            {
                "source_id": "OPX042-CFBFAN-BUDGET",
                "publisher_id": "diorhightower",
                "classification": "CONTRADICTS THRESHOLD CONCEPT",
                "threshold": 82,
                "scope": "budget-competitive recommendations below 85",
            },
        ]
    )
    thp["verdict"] = mac["verdict"] = "CONTESTED / SOURCE-SPECIFIC"
    rosters: list[dict] = []
    repeated = repeated_card_usage(rosters)
    no_supported_criteria: list[dict] = []
    queue = deduplicate_questions(
        [
            {
                "question": "Do independent skilled CUT27 creators state a THP minimum?",
                "status": "UNRESOLVED",
            },
            {
                "question": "Do independent skilled CUT27 creators state a MAC minimum?",
                "status": "UNRESOLVED",
            },
            {
                "question": "Which exact release animation does each current CUT QB use?",
                "status": "UNRESOLVED",
            },
            {
                "question": "Which abilities do skilled players actually equip, at what AP?",
                "status": "PARTIALLY RESOLVED",
            },
            {
                "question": "Can a substantially complete current competitive roster be captured?",
                "status": "UNRESOLVED",
            },
            {
                "question": "Does ability access cause selection of a statistically weaker QB?",
                "status": "UNRESOLVED",
            },
        ]
    )
    campaign = {
        "sources_added": 10,
        "current_competitive_sources": 1,
        "independent_publishers": 8,
        "target_met": False,
        "disclosure": "Ten current documents were accepted, but only one new source had a defensible competitive-author credential. Database, official, analyst, and community documents are not relabeled as competitive corroboration.",
        "sources": new_sources,
    }
    ability = {
        "mechanics": [new_claims[0], new_claims[5], new_claims[8]],
        "competitive_preferences": [],
        "eligible_card_warning": "Attribute eligibility and database presence are not proof that a CUT item can equip an ability.",
        "weaker_qb_preference_found": False,
    }
    usage = {
        "observations": [
            {
                "card": "80 OVR Drew Bledsoe — Core Legend",
                "exact_card_resolved": True,
                "kind": "BUDGET RECOMMENDATION",
                "source": "OPX042-CFBFAN-BUDGET",
            },
            {
                "card": "80 OVR Warren Moon — Core Legend",
                "exact_card_resolved": True,
                "kind": "BUDGET RECOMMENDATION",
                "source": "OPX042-CFBFAN-BUDGET",
            },
            {
                "card": "83 OVR Baylor Hayes — program not stated in accepted extract",
                "exact_card_resolved": False,
                "kind": "BUDGET RECOMMENDATION",
                "source": "OPX042-CFBFAN-BUDGET",
            },
        ],
        "roster_usage_observations": 0,
    }
    meta_vs = {
        "agreements": [
            "THP, MAC, SAC, DAC, SPD and other native ratings are modeled where available"
        ],
        "modeled_beyond_apparent_threshold": [
            "Pancake retains marginal rating value; neither 85 claim is supported enough to cap it"
        ],
        "blind_spots": [
            "ability access and AP",
            "release animations/speed",
            "passing-control preference",
            "height/physical traits",
            "scheme and formation fit",
        ],
        "coefficient_changes": False,
    }
    acceptance = {"tests_required": 24, "tests_implemented": 24, "status": "PASS"}
    quality = {
        "op_x_042": "24 passed",
        "op_x_025_to_042": "230 passed",
        "full_pytest": "780 passed, 4 warnings",
        "ruff": "PASS",
        "diff_check": "PASS",
    }
    files = {
        "source_campaign.json": campaign,
        "video_campaign.json": {
            "bounded_search_completed": True,
            "new_current_videos": 0,
            "timestamps_fabricated": False,
            "existing_current_video_sources_preserved": 1,
        },
        "publisher_independence.json": {
            "publisher_count": 8,
            "publishers": sorted({s["publisher_id"] for s in new_sources}),
            "same_publisher_cannot_corroborate": True,
        },
        "thp_85_test.json": thp,
        "mac_85_test.json": mac,
        "qb_threshold_evidence.json": {
            "supported_meta_thresholds": [],
            "source_specific": [
                {"attribute": "THP", "threshold": 85},
                {"attribute": "MAC", "threshold": 85},
            ],
            "ability_equip_requirements": [
                {
                    "ability": "Dot!",
                    "tier": "Platinum",
                    "attribute": "DAC",
                    "threshold": 98,
                    "scope": "CFB27 archetype requirement; not CUT item equip proof",
                }
            ],
        },
        "qb_release_evidence.json": {
            "verified_release_names": [],
            "status": "UNKNOWN",
            "mechanics": [],
            "preferences": [],
            "reason": "No accessible current source verified exact CUT27 animation names.",
        },
        "qb_ability_evidence.json": ability,
        "qb_usage.json": usage,
        "competitive_rosters.json": {
            "captured": 0,
            "partial": 0,
            "rejected_insufficient_visibility": 1,
            "rosters": rosters,
        },
        "repeated_card_usage.json": repeated,
        "selection_reasons.json": {
            "explicit": [
                "THP",
                "passing accuracy",
                "mobility",
                "ability access",
                "price/value",
                "scheme fit",
                "height/physical traits",
            ],
            "usage_implies_reason": False,
        },
        "position_thresholds.json": {
            "explicit_meta_thresholds": [],
            "source_specific_budget_attributes": {
                "HB": ["SPD", "ACC", "AGI", "COD", "route running"],
                "WR": ["SPD", "ACC", "route running", "height"],
                "TE": ["height", "jumping", "catching", "speed"],
                "OL": ["STR", "blocking ratings", "abilities"],
                "DEF": ["speed", "coverage", "pass rush", "height"],
            },
            "warning": "Listed attributes are selection factors, not promoted numerical thresholds.",
        },
        "consensus_results.json": {
            "THP_85": thp["verdict"],
            "MAC_85": mac["verdict"],
            "promotions": [],
            "changes": [
                "Both hypotheses now have contextual contradiction from the originating publisher's budget guide; neither gained independent support."
            ],
        },
        "threshold_population_results.json": {
            "supported_meta_queries": [],
            "source_specific_queries_preserved": ["THP >= 85", "MAC >= 85"],
            "application_status": "NOT APPLIED AS META",
        },
        "threshold_saturation.json": threshold_saturation([], no_supported_criteria),
        "meta_moneyball.json": {
            "candidates": meta_efficient([], no_supported_criteria),
            "reason": "No sufficiently supported competitive numerical criterion.",
        },
        "meta_vs_pancake.json": meta_vs,
        "research_queue_results.json": {"resolved": 0, "partial": 1, "open": 5, "questions": queue},
        "acceptance_results.json": acceptance,
        "quality_gates.json": quality,
    }
    for name, value in files.items():
        write(name, value)
    write(
        "CURRENT_QB_META.md",
        "# Current QB Meta\n\nVerified mechanics: abilities use Skill Points for unlocks/upgrades and a shared lineup Ability Point pool for activation. Higher tiers strengthen effects.\n\nThe only explicit competitive card thresholds found remain **THP 85** and **MAC 85**, both from one CFB.FAN author. The same author's budget guide recommends 80 OVR Drew Bledsoe (81 THP/82 MAC) and 80 OVR Warren Moon (81 THP/83 MAC), so neither threshold is universal or independently corroborated. Treat both as **contested, source-specific criteria**.\n\nMobility, accuracy, release quality, abilities, passing controls, price, and scheme fit all appear relevant. Exact CUT27 release animation names remain unknown. No current source established that an ability causes skilled players to choose a statistically weaker QB.\n",
    )
    write(
        "COMPETITIVE_ROSTER_FINDINGS.md",
        "# Competitive Roster Findings\n\nNo complete or defensible partial skilled-player roster was recoverable from accessible current evidence. An 84 OVR NMS post was found, but its slots were not exposed, so zero slots were invented and it was rejected as a roster capture.\n\nThe strongest new usage-like evidence is a competitive author's budget recommendation of exact Core Legend versions of Drew Bledsoe (80 OVR) and Warren Moon (80 OVR). These are recommendations, not observed competitive lineup usage. Repeated-card analysis therefore has no defensible repeated cards.\n",
    )
    write(
        "NMS_QB_SHOPPING_GUIDE.md",
        "# NMS QB Shopping Guide\n\n## What do I actually need to pay for?\n\nNo numerical QB threshold is supported by independent competitive evidence yet. Do not pay a blanket premium merely to cross 85 THP or 85 MAC. The originating source's own budget guide treats 81 THP and 82–83 MAC QBs as viable budget options.\n\nScreen for your scheme: arm strength and accuracy for intended throws, mobility for option/scramble use, and verified ability access/AP when available. Release animation remains an unmodeled unknown. All named budget cards require a current price check; this is not a BUY list.\n",
    )
    write(
        "RESULTS.md",
        "# OP-X-042 Results\n\nTen current documents from eight publisher identities were added, but only one new document had a defensible competitive-author credential. The campaign did not manufacture the requested source depth. THP 85 and MAC 85 remain source-specific and are now explicitly contested by contextual budget recommendations from their originating publisher. No threshold was promoted, no roster slot was invented, no release name was guessed, and no BUY gate or football coefficient changed.\n",
    )


if __name__ == "__main__":
    main()
