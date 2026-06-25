from nexus.config import ResearchConfig
from nexus.db import get_conn, init_db
from nexus.llm import LLMClient
from nexus.ingestion.session import create_session
from nexus.agents.genesis import GenesisAgent
from nexus.agents.fetcher import FetcherAgent
from nexus.agents.critic import CriticAgent
from nexus.agents.ranker import RankerAgent
from nexus.agents.evolver import EvolverAgent
from nexus.agents.analogy_bridge import AnalogyBridgeAgent
from nexus.agents.gap_detector import GapDetectorAgent

def _converged(prev_ranked: list, curr_ranked: list, threshold: float = 0.05) -> bool:
    if not prev_ranked or not curr_ranked:
        return False
    prev_ids = [h["hypothesis_id"] for h in prev_ranked[:3]]
    curr_ids = [h["hypothesis_id"] for h in curr_ranked[:3]]
    overlap = len(set(prev_ids) & set(curr_ids))
    score_delta = abs(
        prev_ranked[0]["score"] - curr_ranked[0]["score"]
    ) if prev_ranked and curr_ranked else 1.0
    return overlap >= 2 and score_delta < threshold

def run(goal: str, config: ResearchConfig = None) -> dict:
    if config is None:
        config = ResearchConfig().validate()

    init_db(config)
    conn    = get_conn(config)
    llm     = LLMClient(config)

    genesis  = GenesisAgent(config, llm, conn)
    fetcher  = FetcherAgent(config, llm, conn)
    critic   = CriticAgent(config, llm, conn)
    ranker   = RankerAgent(config, llm, conn)
    evolver  = EvolverAgent(config, llm, conn)
    analogy  = AnalogyBridgeAgent(config, llm, conn)
    gaps     = GapDetectorAgent(config, llm, conn)

    print(f"\n[NEXUS v2] Starting research session")
    print(f"[NEXUS v2] Goal: {goal}")
    print(f"[NEXUS v2] Rounds: {config.max_rounds} | Hypotheses/round: {config.hypotheses_per_round}\n")

    session    = create_session(conn, goal)
    session_id = session["session_id"]
    print(f"[NEXUS v2] Session : {session_id}")
    print(f"[NEXUS v2] Domain  : {session['domain']} | Depth: {session['depth']}")
    print(f"[NEXUS v2] Keywords: {', '.join(session['keywords'])}\n")

    seeds          = []
    prev_ranked    = []
    final_ranked   = []
    final_analogies = {}
    final_gaps     = {}
    round_num      = 1

    for round_num in range(1, config.max_rounds + 1):
        print(f"{'='*54}")
        print(f"[NEXUS v2] Round {round_num}/{config.max_rounds}")
        print(f"{'='*54}")

        print(f"  [1/7] Genesis agent...")
        gen_result = genesis.run(session_id, round_num, {
            "goal"    : session["goal"],
            "domain"  : session["domain"],
            "keywords": session["keywords"],
            "seeds"   : seeds,
            "_summary": f"round {round_num} genesis"
        })
        print(f"        {gen_result['_summary']}")

        print(f"  [2/7] Fetcher agent...")
        fet_result = fetcher.run(session_id, round_num, {
            "hypotheses": gen_result["hypotheses"],
            "keywords"  : session["keywords"],
            "_summary"  : f"round {round_num} fetch"
        })
        print(f"        {fet_result['_summary']}")

        print(f"  [3/7] Critic agent...")
        cri_result = critic.run(session_id, round_num, {
            "hypotheses": gen_result["hypotheses"],
            "_summary"  : f"round {round_num} critic"
        })
        print(f"        {cri_result['_summary']}")

        print(f"  [4/7] Ranker agent...")
        ran_result = ranker.run(session_id, round_num, {
            "critiques": cri_result["critiques"],
            "_summary" : f"round {round_num} ranker"
        })
        print(f"        {ran_result['_summary']}")

        final_ranked = ran_result["ranked"]

        print(f"  [5/7] Analogy bridge agent...")
        ana_result = analogy.run(session_id, round_num, {
            "ranked"  : final_ranked,
            "goal"    : session["goal"],
            "domain"  : session["domain"],
            "_summary": f"round {round_num} analogy"
        })
        print(f"        {ana_result['_summary']}")
        final_analogies = ana_result

        print(f"  [6/7] Gap detector agent...")
        gap_result = gaps.run(session_id, round_num, {
            "ranked"  : final_ranked,
            "goal"    : session["goal"],
            "_summary": f"round {round_num} gaps"
        })
        print(f"        {gap_result['_summary']}")
        final_gaps = gap_result

        if _converged(prev_ranked, final_ranked):
            print(f"\n[NEXUS v2] Converged at round {round_num}. Stopping early.\n")
            break

        if round_num < config.max_rounds:
            print(f"  [7/7] Evolver agent...")
            evo_result = evolver.run(session_id, round_num, {
                "ranked"   : final_ranked,
                "gaps"     : final_gaps,
                "analogies": final_analogies,
                "_summary" : f"round {round_num} evolver"
            })
            seeds = evo_result["seed_texts"]
            print(f"        {evo_result['_summary']}")

        prev_ranked = final_ranked
        print()

    print(f"\n[NEXUS v2] Research complete.")
    print(f"[NEXUS v2] Top hypothesis: {final_ranked[0]['hypothesis_text'][:100] if final_ranked else 'none'}\n")

    return {
        "session_id"      : session_id,
        "goal"            : goal,
        "domain"          : session["domain"],
        "keywords"        : session["keywords"],
        "ranked"          : final_ranked,
        "analogies"       : final_analogies,
        "gaps"            : final_gaps,
        "rounds_completed": round_num,
    }