from nexus.config import ResearchConfig
from nexus.db import get_conn, init_db, get_hypotheses_by_round, get_top_hypotheses
from nexus.llm import LLMClient
from nexus.ingestion.session import create_session
from nexus.agents.genesis import GenesisAgent
from nexus.agents.fetcher import FetcherAgent
from nexus.agents.critic import CriticAgent
from nexus.agents.ranker import RankerAgent
from nexus.agents.evolver import EvolverAgent

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
    conn = get_conn(config)
    llm = LLMClient(config)

    genesis = GenesisAgent(config, llm, conn)
    fetcher = FetcherAgent(config, llm, conn)
    critic  = CriticAgent(config, llm, conn)
    ranker  = RankerAgent(config, llm, conn)
    evolver = EvolverAgent(config, llm, conn)

    print(f"\n[NEXUS] Starting research session")
    print(f"[NEXUS] Goal: {goal}")
    print(f"[NEXUS] Rounds: {config.max_rounds} | Hypotheses/round: {config.hypotheses_per_round}\n")

    session = create_session(conn, goal)
    session_id = session["session_id"]
    print(f"[NEXUS] Session: {session_id}")
    print(f"[NEXUS] Domain: {session['domain']} | Depth: {session['depth']}")
    print(f"[NEXUS] Keywords: {', '.join(session['keywords'])}\n")

    seeds = []
    prev_ranked = []
    final_ranked = []

    for round_num in range(1, config.max_rounds + 1):
        print(f"{'='*50}")
        print(f"[NEXUS] Round {round_num}/{config.max_rounds}")
        print(f"{'='*50}")

        print(f"  [1/5] Genesis agent...")
        gen_result = genesis.run(session_id, round_num, {
            "goal": session["goal"],
            "domain": session["domain"],
            "keywords": session["keywords"],
            "seeds": seeds,
            "_summary": f"round {round_num} genesis"
        })
        print(f"        {gen_result['_summary']}")

        print(f"  [2/5] Fetcher agent...")
        fet_result = fetcher.run(session_id, round_num, {
            "hypotheses": gen_result["hypotheses"],
            "keywords": session["keywords"],
            "_summary": f"round {round_num} fetch"
        })
        print(f"        {fet_result['_summary']}")

        print(f"  [3/5] Critic agent...")
        cri_result = critic.run(session_id, round_num, {
            "hypotheses": gen_result["hypotheses"],
            "_summary": f"round {round_num} critic"
        })
        print(f"        {cri_result['_summary']}")

        print(f"  [4/5] Ranker agent...")
        ran_result = ranker.run(session_id, round_num, {
            "critiques": cri_result["critiques"],
            "_summary": f"round {round_num} ranker"
        })
        print(f"        {ran_result['_summary']}")

        final_ranked = ran_result["ranked"]

        if _converged(prev_ranked, final_ranked):
            print(f"\n[NEXUS] Converged at round {round_num}. Stopping early.\n")
            break

        if round_num < config.max_rounds:
            print(f"  [5/5] Evolver agent...")
            evo_result = evolver.run(session_id, round_num, {
                "ranked": final_ranked,
                "_summary": f"round {round_num} evolver"
            })
            seeds = evo_result["seed_texts"]
            print(f"        {evo_result['_summary']}")

        prev_ranked = final_ranked
        print()

    print(f"\n[NEXUS] Research complete.")
    print(f"[NEXUS] Top hypothesis: {final_ranked[0]['hypothesis_text'][:100] if final_ranked else 'none'}\n")

    return {
        "session_id": session_id,
        "goal": goal,
        "domain": session["domain"],
        "keywords": session["keywords"],
        "ranked": final_ranked,
        "rounds_completed": round_num,
    }
