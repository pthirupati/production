"""RAG retrieval and grounded LLM chat in the AI/ML V2 facades.

The 2026-08 audit (A4) found `rag_retrieve` returned the same 3 hardcoded chunks
with scores fabricated as `0.93 - i*0.04`, and `llm_chat` echoed the prompt with
tokens faked as `len(prompt)//4`. These tests pin the properties that separate
real retrieval from that stub: results must change with the query, scores must
be derived from the text, and an out-of-corpus query must return nothing.
"""

from django.test import SimpleTestCase

from apps.vmware_sim.aiml_v2_facades import (
    apply_v2_action,
    build_index,
    count_tokens,
    rag_search,
    seed_v2,
)


class RagRetrievalTests(SimpleTestCase):
    def _retrieve(self, query, **payload):
        state = seed_v2()
        result = apply_v2_action(state, "rag_retrieve", {"query": query, **payload})
        self.assertTrue(result["ok"], result)
        return state, result

    def test_different_queries_return_different_chunks(self):
        """The stub returned the same 3 sources for every query."""
        _, refund = self._retrieve("What is the refund policy for digital products?")
        _, gpu = self._retrieve("gpu tokens per second falling, thermal throttling")

        refund_sources = {r["source"] for r in refund["results"]}
        gpu_sources = {r["source"] for r in gpu["results"]}

        self.assertTrue(refund_sources)
        self.assertTrue(gpu_sources)
        self.assertFalse(
            refund_sources & gpu_sources,
            f"unrelated queries shared chunks: {refund_sources & gpu_sources}",
        )
        self.assertTrue(any("refund-policy" in s for s in refund_sources), refund_sources)
        self.assertTrue(any("RB-204" in s for s in gpu_sources), gpu_sources)

    def test_top_result_matches_query_topic(self):
        _, result = self._retrieve("service crashes and restarts under high load")
        self.assertIn("RB-112", result["results"][0]["source"])

    def test_scores_are_not_the_fabricated_arithmetic_series(self):
        """Stub scores were exactly 0.93, 0.89, 0.85 regardless of input."""
        _, result = self._retrieve("What is the refund policy for digital products?")
        scores = [r["score"] for r in result["results"]]
        self.assertGreaterEqual(len(scores), 2)
        self.assertNotEqual(scores[:3], [0.93, 0.89, 0.85])
        # A fabricated series has a constant gap; real cosine scores do not.
        gaps = [round(scores[i] - scores[i + 1], 3) for i in range(len(scores) - 1)]
        self.assertGreater(len(set(gaps)), 1, f"scores look synthetic: {scores}")

    def test_scores_respond_to_the_query(self):
        """Not a fixed table: the same chunk scores differently per query.

        Note a shorter query can legitimately score *higher* — one term out of
        one matching beats three out of six — so this compares one chunk across
        queries rather than assuming longer queries score better.
        """
        _, on_topic = self._retrieve("digital refund policy download 14 days")
        _, off_topic = self._retrieve("refund license termination abuse accounts")

        def score_for(result, needle):
            return next(
                (r["score"] for r in result["results"] if needle in r["source"]), None
            )

        policy_on = score_for(on_topic, "refund-policy")
        policy_off = score_for(off_topic, "refund-policy")
        self.assertIsNotNone(policy_on)
        if policy_off is not None:
            self.assertNotEqual(policy_on, policy_off)
        self.assertIn("terms-of-service", off_topic["results"][0]["source"])

    def test_out_of_corpus_query_retrieves_nothing(self):
        """A stub always had something to return; real retrieval can miss."""
        _, result = self._retrieve("zzzqqq unrelated nonsense xyzzy")
        self.assertEqual(result["results"], [])
        self.assertIn("No chunks", result["message"])

    def test_top_k_is_honoured(self):
        _, result = self._retrieve("refund policy digital products", top_k=2)
        self.assertLessEqual(len(result["results"]), 2)
        self.assertEqual(result["params"]["top_k"], 2)

    def test_retrieval_is_deterministic_across_calls(self):
        """Graders replay labs; hash()-based embedding would break this."""
        first = rag_search("refund policy for digital products")
        second = rag_search("refund policy for digital products")
        self.assertEqual(first, second)

    def test_chunk_size_and_overlap_change_the_index(self):
        small = build_index(chunk_size=20, overlap=0)
        large = build_index(chunk_size=400, overlap=0)
        self.assertGreater(len(small), len(large))
        overlapped = build_index(chunk_size=20, overlap=10)
        self.assertGreater(len(overlapped), len(small))

    def test_overlap_is_clamped_below_chunk_size(self):
        """overlap >= chunk_size would make the sliding window never advance."""
        _, result = self._retrieve("refund policy", chunk_size=20, overlap=99)
        self.assertLess(result["params"]["overlap"], result["params"]["chunk_size"])

    def test_disabling_rerank_changes_ranking(self):
        with_rerank = rag_search("refund policy for digital products", rerank=True)
        without = rag_search("refund policy for digital products", rerank=False)
        self.assertNotEqual(
            [r["source"] for r in with_rerank] + [r["score"] for r in with_rerank],
            [r["source"] for r in without] + [r["score"] for r in without],
        )

    def test_state_records_query_and_params(self):
        state, _ = self._retrieve("refund policy")
        self.assertEqual(state["rag_last_query"], "refund policy")
        self.assertIn("chunk_size", state["rag_params"])
        self.assertEqual(state["rag_results"][0]["source"].count("chunk"), 1)

    def test_seeded_knowledge_base_counts_match_the_real_corpus(self):
        kb = seed_v2()["knowledge_bases"][0]
        self.assertEqual(kb["chunks"], len(build_index()))
        self.assertGreater(kb["documents"], 0)


class LlmChatTests(SimpleTestCase):
    def _chat(self, prompt, **payload):
        state = seed_v2()
        result = apply_v2_action(state, "llm_chat", {"prompt": prompt, **payload})
        self.assertTrue(result["ok"], result)
        return state, result

    def test_response_is_grounded_in_retrieved_text_not_the_prompt(self):
        """The stub responded with `Based on the lab knowledge base: {prompt[:120]}`."""
        prompt = "why does the inference service keep restarting under high load"
        _, result = self._chat(prompt)
        self.assertTrue(result["grounded"])
        self.assertNotIn("Based on the lab knowledge base", result["response"])
        # Content the model could only have from the corpus, not from the prompt.
        self.assertIn("OOM killer", result["response"])
        self.assertTrue(any("RB-112" in s for s in result["sources"]))

    def test_unanswerable_prompt_refuses_instead_of_fabricating(self):
        _, result = self._chat("zzzqqq unrelated nonsense xyzzy")
        self.assertFalse(result["grounded"])
        self.assertEqual(result["sources"], [])
        self.assertIn("no chunk matching", result["response"])

    def test_different_prompts_produce_different_answers(self):
        _, crash = self._chat("why does the service restart under load")
        _, refund = self._chat("how long does a digital refund take")
        self.assertNotEqual(crash["response"], refund["response"])

    def test_token_usage_is_not_character_count_over_four(self):
        prompt = "how long does a digital refund take"
        _, result = self._chat(prompt)
        self.assertNotEqual(result["usage"]["input"], max(1, len(prompt) // 4))
        self.assertNotEqual(
            result["usage"]["output"], max(1, len(result["response"]) // 4)
        )

    def test_input_tokens_include_the_retrieved_context(self):
        """Context is what a real pipeline actually pays for."""
        grounded_prompt = "how long does a digital refund take"
        _, grounded = self._chat(grounded_prompt)
        self.assertGreater(grounded["usage"]["input"], count_tokens(grounded_prompt))

        _, ungrounded = self._chat("zzzqqq nonsense xyzzy")
        self.assertEqual(ungrounded["usage"]["input"], count_tokens("zzzqqq nonsense xyzzy"))

    def test_token_count_scales_with_words_not_characters(self):
        self.assertEqual(count_tokens(""), 0)
        short = count_tokens("the cat sat")
        longer = count_tokens("the cat sat on the mat in the sun")
        self.assertGreater(longer, short)
        # A long single word must not cost the same as many short words.
        self.assertLess(count_tokens("antidisestablishmentarianism"), count_tokens("a b c d e f g h"))

    def test_playground_state_records_sources_and_usage(self):
        state, _ = self._chat("how long does a digital refund take")
        playground = state["llm_playground"]
        self.assertTrue(playground["last_sources"])
        self.assertTrue(playground["last_grounded"])
        self.assertGreater(playground["token_usage"]["input"], 0)
        self.assertGreater(playground["token_usage"]["output"], 0)

    def test_empty_prompt_is_rejected(self):
        state = seed_v2()
        self.assertEqual(
            apply_v2_action(state, "llm_chat", {"prompt": "   "}),
            {"ok": False, "error": "prompt required"},
        )
