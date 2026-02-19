"""
Sovereign AI Scientist — Verifiable Research Discovery Agent
Built on EigenCloud: EigenAI (deterministic inference) + EigenCompute (TEE)

Every LLM decision is deterministic and independently verifiable.
Same prompt + same seed + same model = same output. Always.

Auth: Uses deTERMinal grant-based wallet signature authentication.
"""

import json
import hashlib
import time
import re
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from dataclasses import dataclass, asdict
from typing import List, Optional, Callable


DETERMINAL_API = "https://determinal-api.eigenarcade.com"


@dataclass
class AuditEntry:
    step_id: str
    timestamp: float
    milestone: str
    action: str
    prompt_hash: str
    output_hash: str
    output_preview: str
    model: str
    seed: int
    full_prompt: str = ""
    full_output: str = ""
    verified: bool = False
    verification_match: Optional[bool] = None


class EigenAIClient:
    """
    EigenAI client using deTERMinal grant-based authentication.
    
    Flow:
    1. Fetch grant message from deTERMinal
    2. Sign with wallet private key
    3. Include signature in every API request
    """

    def __init__(self, wallet_address: str, private_key: str):
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.grant_message = None
        self.grant_signature = None
        self._authenticate()

    def _authenticate(self):
        """Fetch grant message and sign it."""
        # Step 1: Get the grant message
        resp = requests.get(
            f"{DETERMINAL_API}/message",
            params={"address": self.wallet_address},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("success"):
            raise RuntimeError(f"Failed to get grant message: {data}")
        
        self.grant_message = data["message"]

        # Step 2: Sign the message with wallet private key
        message = encode_defunct(text=self.grant_message)
        signed = Account.sign_message(message, private_key=self.private_key)
        self.grant_signature = signed.signature.hex()
        if not self.grant_signature.startswith("0x"):
            self.grant_signature = "0x" + self.grant_signature

    def chat_completion(
        self,
        model: str,
        messages: list,
        seed: int = 42,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> dict:
        """Make a chat completion request via deTERMinal grant auth."""
        payload = {
            "model": model,
            "messages": messages,
            "seed": seed,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Grant auth fields
            "grantMessage": self.grant_message,
            "grantSignature": self.grant_signature,
            "walletAddress": self.wallet_address,
        }

        resp = requests.post(
            f"{DETERMINAL_API}/api/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def check_grant(self) -> dict:
        """Check remaining token balance."""
        resp = requests.get(
            f"{DETERMINAL_API}/checkGrant",
            params={"address": self.wallet_address},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


class SovereignScientist:
    """
    Autonomous research agent with verifiable compute guarantees.

    Architecture:
    - All LLM calls → EigenAI via deTERMinal (deterministic, verifiable)
    - Every call is hashed and logged in an audit trail
    - Any step can be independently re-executed to verify correctness
    - Designed to run inside EigenCompute TEE for code integrity
    """

    def __init__(
        self,
        wallet_address: str,
        private_key: str,
        model: str = "gpt-oss-120b-f16",
        seed: int = 42,
    ):
        self.client = EigenAIClient(wallet_address, private_key)
        self.model = model
        self.seed = seed
        self.audit_log: List[AuditEntry] = []
        self.step_counter = 0

    # ──────────────────────────────────────────────────
    # CORE: Verifiable inference wrapper
    # ──────────────────────────────────────────────────

    def _call(self, messages: list, milestone: str, action: str) -> str:
        """
        Every LLM call goes through here. Every call is:
        1. Hashed (input + output)
        2. Logged in the audit trail
        3. Reproducible via EigenAI determinism
        """
        self.step_counter += 1
        step_id = f"{milestone}_{self.step_counter:03d}"

        prompt_str = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        prompt_hash = hashlib.sha256(prompt_str.encode()).hexdigest()

        # Retry once on failure — EigenAI is mainnet alpha
        last_error = None
        for attempt in range(2):
            try:
                response = self.client.chat_completion(
                    model=self.model,
                    messages=messages,
                    seed=self.seed,
                    temperature=0.0,
                    max_tokens=4096,
                )
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    time.sleep(2)
        else:
            raise RuntimeError(
                f"EigenAI call failed after 2 attempts ({action}): {last_error}"
            )

        # Extract output text from response
        output = ""
        try:
            output = response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            output = str(response)

        # Strip model's chain-of-thought / channel tokens from ALL outputs
        # Must use _strip_tokens() so verify_step applies identical stripping.
        output = self._strip_tokens(output)

        output_hash = hashlib.sha256(output.encode()).hexdigest()

        entry = AuditEntry(
            step_id=step_id,
            timestamp=time.time(),
            milestone=milestone,
            action=action,
            prompt_hash=prompt_hash,
            output_hash=output_hash,
            output_preview=output[:300],
            model=self.model,
            seed=self.seed,
            full_prompt=prompt_str,
            full_output=output,
        )
        self.audit_log.append(entry)
        return output

    def _parse_json(self, raw: str) -> dict | list:
        """Robustly parse JSON from LLM output, even with chain-of-thought noise."""
        clean = raw.strip()
        # Strip harmony/channel tokens like <|channel|>analysis<|message|>
        clean = re.sub(r"<\|[^|]*\|>", "", clean).strip()
        # Strip markdown fences
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            clean = clean.rsplit("```", 1)[0]
            clean = clean.strip()

        # Try direct parse first
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Find the first JSON array [...] or object {...} in the text
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start = clean.find(start_char)
            if start == -1:
                continue
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(clean)):
                c = clean[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == start_char:
                    depth += 1
                elif c == end_char:
                    depth -= 1
                    if depth == 0:
                        candidate = clean[start:i+1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

        # Last resort: strip everything before first { or [
        for ch in ['{', '[']:
            idx = clean.find(ch)
            if idx != -1:
                try:
                    return json.loads(clean[idx:])
                except json.JSONDecodeError:
                    pass

        raise json.JSONDecodeError("No valid JSON found", clean, 0)

    # ──────────────────────────────────────────────────
    # VERIFICATION: The killer feature
    # ──────────────────────────────────────────────────

    def _strip_tokens(self, raw: str) -> str:
        """Apply the same token stripping used in _call(). Must be identical."""
        output = re.sub(
            r"<\|channel\|>\s*analysis\s*<\|message\|>.*?<\|end\|>",
            "", raw, flags=re.DOTALL
        ).strip()
        output = re.sub(r"<\|[^|]*\|>", "", output).strip()
        return output

    def verify_step(self, step_id: str) -> dict:
        """
        Re-execute a step on EigenAI and compare output hashes.

        EigenAI is deterministic by design (docs: bit-for-bit identical output
        for same model + prompt + seed). This re-executes the exact same call
        and applies the same token stripping as the original _call(), then
        compares SHA256 hashes. A match proves the agent ran as committed.
        """
        entry = next((e for e in self.audit_log if e.step_id == step_id), None)
        if not entry:
            return {"error": f"Step {step_id} not found"}

        original_messages = json.loads(entry.full_prompt)

        # Re-execute on EigenAI with identical parameters
        response = self.client.chat_completion(
            model=entry.model,
            messages=original_messages,
            seed=entry.seed,
            temperature=0.0,
            max_tokens=4096,
        )

        raw_output = ""
        try:
            raw_output = response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raw_output = str(response)

        # Apply IDENTICAL stripping as _call() — this was the original bug:
        # verify_step hashed raw output while _call() hashed stripped output.
        new_output = self._strip_tokens(raw_output)
        new_hash = hashlib.sha256(new_output.encode()).hexdigest()
        match = new_hash == entry.output_hash

        entry.verified = True
        entry.verification_match = match

        return {
            "step_id": step_id,
            "original_hash": entry.output_hash,
            "verification_hash": new_hash,
            "match": match,
            "model": entry.model,
            "seed": entry.seed,
            "prompt_hash": entry.prompt_hash,
            "status": "VERIFIED ✓" if match else "MISMATCH ✗",
        }

    # ──────────────────────────────────────────────────
    # M1: HYPOTHESIS GENERATION
    # ──────────────────────────────────────────────────

    def generate_hypotheses(self, topic: str, n: int = 3) -> list:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert AI research scientist. "
                    "Generate novel, testable research hypotheses.\n\n"
                    "For each hypothesis, output a JSON array where each element has:\n"
                    '- "title": concise title\n'
                    '- "description": 2-3 sentence description\n'
                    '- "novelty": why this is novel\n'
                    '- "testable_prediction": specific measurable prediction\n'
                    '- "experiment_sketch": brief experiment design\n'
                    '- "risk": what could go wrong\n\n'
                    "IMPORTANT: Output ONLY the JSON array. "
                    "Do NOT include any reasoning, explanation, or chain-of-thought. "
                    "Start your response with [ and end with ]."
                ),
            },
            {"role": "user", "content": f"Topic: {topic}\nGenerate {n} hypotheses."},
        ]

        raw = self._call(messages, "M1_IDEATION", "generate_hypotheses")
        try:
            return self._parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            return [{"title": "Generation completed", "raw_output": raw[:500]}]

    def assess_novelty(self, hypothesis: dict) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research novelty assessor. "
                    "Given a hypothesis, assess novelty on 1-10 scale.\n\n"
                    "Output JSON: "
                    '{"score": int, "reasoning": str, "related_work": [str], "differentiators": [str]}\n\n'
                    "IMPORTANT: Output ONLY the JSON object. "
                    "Do NOT include any reasoning or chain-of-thought. "
                    "Start your response with { and end with }."
                ),
            },
            {"role": "user", "content": json.dumps(hypothesis)},
        ]

        raw = self._call(messages, "M1_IDEATION", "assess_novelty")
        try:
            result = self._parse_json(raw)
            # Ensure we always return a dict
            if isinstance(result, list):
                result = result[0] if result and isinstance(result[0], dict) else {"score": 5}
            if not isinstance(result, dict):
                result = {"score": 5, "reasoning": str(result)[:300]}
            return result
        except (json.JSONDecodeError, ValueError):
            return {"score": 5, "reasoning": raw[:300]}

    # ──────────────────────────────────────────────────
    # M2: EXPERIMENT DESIGN
    # ──────────────────────────────────────────────────

    def design_experiment(self, hypothesis: dict) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an ML experiment designer. "
                    "Design a rigorous experiment to test this hypothesis.\n\n"
                    "Output JSON with:\n"
                    '- "method": description of proposed method\n'
                    '- "baselines": [list of baseline methods]\n'
                    '- "datasets": [datasets/environments]\n'
                    '- "metrics": [evaluation metrics]\n'
                    '- "hyperparameters": key hyperparams\n'
                    '- "ablations": [ablation studies]\n'
                    '- "compute_estimate_gpu_hours": number\n'
                    '- "expected_results": what would confirm/reject hypothesis\n\n'
                    "IMPORTANT: Output ONLY the JSON object. "
                    "Do NOT include any reasoning or chain-of-thought. "
                    "Start your response with { and end with }."
                ),
            },
            {"role": "user", "content": json.dumps(hypothesis)},
        ]

        raw = self._call(messages, "M2_DESIGN", "design_experiment")
        try:
            result = self._parse_json(raw)
            if isinstance(result, list):
                result = result[0] if result and isinstance(result[0], dict) else {"method": str(result)[:500]}
            return result if isinstance(result, dict) else {"method": str(result)[:500]}
        except (json.JSONDecodeError, ValueError):
            return {"method": raw[:500]}

    def generate_code(self, experiment: dict) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert ML engineer. "
                    "Generate a complete, runnable Python experiment script.\n"
                    "Use PyTorch. Include training loop, evaluation, result logging.\n"
                    "Output results as JSON to stdout.\n"
                    "Keep it self-contained and under 150 lines.\n"
                    "Output ONLY the Python code, no markdown."
                ),
            },
            {"role": "user", "content": json.dumps(experiment)},
        ]

        return self._call(messages, "M2_DESIGN", "generate_code")

    # ──────────────────────────────────────────────────
    # M3: RESULT ANALYSIS
    # ──────────────────────────────────────────────────

    def analyze_results(self, hypothesis: dict, results: dict) -> dict:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a rigorous ML researcher analyzing experiment results.\n"
                    "Determine:\n"
                    "- Whether the hypothesis is supported\n"
                    "- Statistical significance\n"
                    "- Key findings\n"
                    "- Limitations\n"
                    "- Follow-up experiments\n\n"
                    "Be honest. If results don't support the hypothesis, say so.\n\n"
                    "Output JSON: "
                    '{"verdict": str, "confidence": float 0-1, '
                    '"key_findings": [str], "limitations": [str], "follow_ups": [str]}\n\n'
                    "IMPORTANT: Output ONLY the JSON object. "
                    "Do NOT include any reasoning or chain-of-thought. "
                    "Start your response with { and end with }."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"hypothesis": hypothesis, "results": results}
                ),
            },
        ]

        raw = self._call(messages, "M3_ANALYSIS", "analyze_results")
        try:
            result = self._parse_json(raw)
            if isinstance(result, list):
                result = result[0] if result and isinstance(result[0], dict) else {"verdict": str(result)[:300]}
            return result if isinstance(result, dict) else {"verdict": str(result)[:300]}
        except (json.JSONDecodeError, ValueError):
            return {"verdict": raw[:300]}

    # ──────────────────────────────────────────────────
    # M4: PAPER WRITING
    # ──────────────────────────────────────────────────

    def write_abstract(self, hypothesis: dict, results: dict, analysis: dict) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an academic paper writer. "
                    "Write a concise, compelling abstract (under 250 words).\n"
                    "Structure: context → problem → method → results → impact.\n"
                    "Be specific about numbers and claims."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "hypothesis": hypothesis,
                        "results": results,
                        "analysis": analysis,
                    }
                ),
            },
        ]

        return self._call(messages, "M4_WRITING", "write_abstract")

    # ──────────────────────────────────────────────────
    # FULL PIPELINE
    # ──────────────────────────────────────────────────

    def run_pipeline(
        self,
        topic: str,
        on_milestone: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Execute the complete verifiable research program."""

        def _notify(ms: str):
            if on_milestone:
                on_milestone(ms)

        # ── M1: Ideation ─────────────────────────────
        _notify("M1_IDEATION")
        hypotheses = self.generate_hypotheses(topic)

        novelty_scores = []
        for h in hypotheses:
            if isinstance(h, dict) and "title" in h:
                score = self.assess_novelty(h)
                novelty_scores.append(score)
            else:
                novelty_scores.append({"score": 0})

        best_idx = 0
        best_score = -1
        for i, ns in enumerate(novelty_scores):
            # Handle case where parser returns list instead of dict
            if isinstance(ns, list) and len(ns) > 0:
                ns = ns[0] if isinstance(ns[0], dict) else {"score": 5}
            if not isinstance(ns, dict):
                ns = {"score": 5}
            s = ns.get("score", 0)
            if isinstance(s, (int, float)) and s > best_score:
                best_score = s
                best_idx = i

        selected = hypotheses[best_idx] if hypotheses else {}

        # ── M2: Design ───────────────────────────────
        _notify("M2_DESIGN")
        experiment = self.design_experiment(selected)
        code = self.generate_code(experiment)

        # ── M3: Analysis ─────────────────────────────
        _notify("M3_ANALYSIS")
        sim_results = {
            "baseline": {"mean_reward": 145.3, "std": 12.1, "success_rate": 0.72},
            "proposed": {"mean_reward": 178.9, "std": 9.8, "success_rate": 0.84},
            "improvement": "+23.1% reward, +16.7% success rate",
            "statistical_test": "p < 0.01 (Welch's t-test)",
            "note": "Simulated for demo. Real execution runs in EigenCompute TEE.",
        }
        analysis = self.analyze_results(selected, sim_results)

        # ── M4: Writing ──────────────────────────────
        _notify("M4_WRITING")
        abstract = self.write_abstract(selected, sim_results, analysis)

        # ── Provenance ───────────────────────────────
        _notify("DONE")
        program_hash = hashlib.sha256(topic.encode()).hexdigest()

        return {
            "program": {
                "topic": topic,
                "program_hash": program_hash,
                "model": self.model,
                "seed": self.seed,
            },
            "milestones": {
                "M1_IDEATION": {
                    "hypotheses": hypotheses,
                    "novelty_scores": novelty_scores,
                    "selected": selected,
                },
                "M2_DESIGN": {
                    "experiment": experiment,
                    "code_preview": code[:500] if isinstance(code, str) else "",
                },
                "M3_ANALYSIS": {
                    "results": sim_results,
                    "analysis": analysis,
                },
                "M4_WRITING": {
                    "abstract": abstract,
                },
            },
            "provenance": {
                "total_steps": len(self.audit_log),
                "all_hashes": [
                    {
                        "step": e.step_id,
                        "action": e.action,
                        "prompt_hash": e.prompt_hash[:16] + "...",
                        "output_hash": e.output_hash[:16] + "...",
                    }
                    for e in self.audit_log
                ],
                "verification": (
                    "Every step can be independently re-executed on EigenAI. "
                    "Same prompt + same seed = same output hash. Provably."
                ),
            },
        }

    def get_audit_log(self) -> list:
        return [asdict(e) for e in self.audit_log]
