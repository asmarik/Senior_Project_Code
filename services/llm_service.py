"""LLM-powered services using OpenAI API (GPT-4o-mini)"""
import re
import json
from typing import List, Dict, Any
from models import model_manager


def _extract_relevant_context(pdf_text: str, clause_text: str, max_size: int = 2500) -> str:
    """
    Intelligently extract the most relevant sections of the PDF text for a given clause.

    - Smaller max_size (default 2500 chars) for sharper LLM focus.
    - Smaller header portion (intro/scope/definitions).
    - Scores chunks by keyword density related to the clause.
    """
    if len(pdf_text) <= max_size:
        return pdf_text

    # Always include the first ~800 chars (usually intro, scope, definitions)
    header_size = min(800, max_size // 3)
    header = pdf_text[:header_size]

    # Extract meaningful keywords from clause
    clause_keywords = set()
    stopwords = {
        "article", "shall", "must", "should", "with", "from", "that", "this",
        "have", "been", "will", "for", "such", "as", "and", "the", "data",
        "personal", "controller", "processing",
    }
    for word in clause_text.lower().split():
        clean_word = re.sub(r"[^\w\s]", "", word)
        if len(clean_word) > 3 and clean_word not in stopwords:
            clause_keywords.add(clean_word)

    remaining_text = pdf_text[header_size:]
    chunk_size = 800
    chunks = []

    for i in range(0, len(remaining_text), chunk_size):
        chunk = remaining_text[i: i + chunk_size]
        chunks.append(
            {
                "text": chunk,
                "start": header_size + i,
                "score": 0.0,
            }
        )

    # Score chunks by keyword density (matches per 1k chars)
    for chunk in chunks:
        chunk_lower = chunk["text"].lower()
        if not clause_keywords:
            chunk["score"] = 0.0
            continue

        matches = sum(1 for kw in clause_keywords if kw in chunk_lower)
        density = matches / (len(chunk["text"]) / 1000 + 1e-6)
        chunk["score"] = density

    # Sort by score (highest first)
    chunks.sort(key=lambda c: c["score"], reverse=True)

    # Combine header + best chunks up to max_size
    context_parts = [header]
    current_size = len(header)

    for chunk in chunks:
        if current_size >= max_size or chunk["score"] == 0:
            break

        available = max_size - current_size
        if available <= 0:
            break

        text_to_add = chunk["text"][:available]
        context_parts.append(text_to_add)
        current_size += len(text_to_add)

    result = "\n\n[...sections selected for relevance...]\n\n".join(context_parts)

    # Safety trim
    if len(result) > max_size:
        result = result[:max_size]

    return result


def llm_clause_match(
    clause_text: str,
    pdf_text: str,
    article_number: int,
    clause_label: str,
) -> Dict[str, Any]:
    """
    Use OpenAI API to determine if a PDPL clause is covered in the PDF.

    Returns:
        dict with:
        - score: Coverage score (0-1)
        - score_percentage: 0-100 int
        - explanation: Brief explanation of the match/gap
        - confidence: LLM confidence (high/medium/low)
    """
    # Check if LLM clause matching is enabled
    if not model_manager.llm_clause_matching or not model_manager.llm_enabled:
        return None

    if not model_manager.openai_client:
        return None

    try:
        # DEBUG: Log PDF text length
        print(f"[LLM DEBUG] Article {article_number}, Clause {clause_label}:")
        print(f"[LLM DEBUG] Total PDF text length: {len(pdf_text)} characters")

        # Use smaller, sharper context window
        max_context_size = 4000

        if len(pdf_text) <= max_context_size:
            pdf_context = pdf_text
            print(f"[LLM DEBUG] Using full PDF text: {len(pdf_context)} characters")
        else:
            pdf_context = _extract_relevant_context(
                pdf_text=pdf_text,
                clause_text=clause_text,
                max_size=max_context_size,
            )
            print(
                f"[LLM DEBUG] Using smart-extracted context: {len(pdf_context)} characters "
                f"(from {len(pdf_text)} total)"
            )

        # Prompt
                # Prompt
        prompt = f"""
You are a senior legal compliance expert specializing in PDPL (Saudi Personal Data Protection Law).
Your task is to evaluate whether a specific PDPL clause is adequately covered in a given privacy policy.

-------------------------------------
SCORING RULES (LENIENT AND FAIR):
0–19 = Not covered or almost completely missing.
20–49 = Mentioned briefly or very partially; important elements missing.
50–79 = Generally covered; the main idea is present, even if some details are missing.
80–100 = Strong coverage; clearly addresses the requirement with good detail.

EVALUATION GUIDELINES (BE GENEROUS BUT REALISTIC):
- Look for EQUIVALENT MEANING, not exact wording. Policies rarely copy PDPL text.
- If the core idea of the clause is clearly there, you should normally score **at least 60**.
- If the policy is detailed and aligns well with the clause, typical scores are **75–95**.
- Use scores below 40 **only** when the requirement is truly missing or extremely vague.
- If you are unsure but see some connection, stay in the **40–60** range instead of very low.
- The explanation must be ONE short sentence, neutral and factual.

-------------------------------------
FEW-SHOT EXAMPLES (FOLLOW THIS PATTERN EXACTLY):

EXAMPLE 1 — Good Coverage
PDPL Clause: "The controller must inform the data subject of the purpose of data collection."
Policy Text: "We collect personal data to provide services, improve our products, comply with legal obligations, and enhance your experience."
OUTPUT:
SCORE: 88
CONFIDENCE: high
EXPLANATION: The policy clearly explains why data is collected and matches the intent of the clause.

EXAMPLE 2 — Partial but Acceptable Coverage
PDPL Clause: "The data subject must be notified when personal data is transferred outside the Kingdom."
Policy Text: "We may share your information with international partners and group companies in other countries."
OUTPUT:
SCORE: 62
CONFIDENCE: medium
EXPLANATION: The policy mentions international transfers but does not clearly state that the data subject will be notified.

EXAMPLE 3 — Weak Coverage
PDPL Clause: "The controller must provide a mechanism to stop receiving marketing messages."
Policy Text: "We may send you promotional and marketing content."
OUTPUT:
SCORE: 18
CONFIDENCE: high
EXPLANATION: The policy mentions marketing but does not provide any opt-out mechanism.

EXAMPLE 4 — Strong Coverage
PDPL Clause: "The controller must notify the competent authority in case of a data breach."
Policy Text: "If a personal data breach occurs, we will promptly notify the competent Saudi authority and affected individuals in accordance with PDPL."
OUTPUT:
SCORE: 95
CONFIDENCE: high
EXPLANATION: The policy explicitly commits to notifying the authority and affected individuals in case of a breach.

-------------------------------------
NOW EVALUATE THE FOLLOWING:

PDPL REQUIREMENT TO CHECK
Article: {article_number}
Clause: {clause_label}
Clause Text:
{clause_text}

PRIVACY POLICY TEXT:
{pdf_context}

-------------------------------------
Return the answer in EXACTLY this format:

SCORE: <0-100>
CONFIDENCE: <high/medium/low>
EXPLANATION: <one concise sentence>
"""



        # Generate response using OpenAI (optimized for speed)
        response = model_manager.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior legal compliance expert specializing in PDPL (Saudi Personal Data Protection Law).",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,  # Increased for more variation (0.0 = deterministic, 1.0 = creative)
            max_tokens=150,
            timeout=10,
        )

        response_text = response.choices[0].message.content.strip()

        # Debug: Print raw response
        print(f"[LLM RAW] Article {article_number}, Clause {clause_label}:")
        print(f"Response: {response_text[:150]}...")

        # Parse the LLM response
        score = 0
        confidence = "medium"
        explanation = ""

        # Extract SCORE
        score_match = re.search(r"SCORE:\s*(\d+)", response_text, re.IGNORECASE)
        if score_match:
            score = min(100, max(0, int(score_match.group(1))))
        else:
            print("[WARNING] Could not extract SCORE from LLM response")

        # Extract CONFIDENCE
        conf_match = re.search(
            r"CONFIDENCE:\s*(high|medium|low)", response_text, re.IGNORECASE
        )
        if conf_match:
            confidence = conf_match.group(1).lower()

        # Extract EXPLANATION
        exp_match = re.search(
            r"EXPLANATION:\s*(.+?)(?:\n\n|\nSCORE:|\nCONFIDENCE:|\Z)",
            response_text,
            re.IGNORECASE | re.DOTALL,
        )
        if exp_match:
            explanation = exp_match.group(1).strip()
            explanation = " ".join(explanation.split())
        else:
            fallback_match = re.search(
                r"EXPLANATION:\s*(.+)", response_text, re.IGNORECASE
            )
            if fallback_match:
                explanation = " ".join(fallback_match.group(1).strip().split())
            else:
                explanation = "LLM provided score but no explanation"

        print(
            f"[LLM PARSED] Score={score}, Confidence={confidence}, "
            f"Explanation={explanation[:80]}..."
        )

        return {
            "score": score / 100.0,  # Convert to 0-1 range
            "score_percentage": score,
            "explanation": explanation,
            "confidence": confidence,
            "method": "llm_openai_gpt4o_mini",
        }

    except Exception as e:
        print(f"[WARNING] LLM clause matching failed: {e}")
        return None


def llm_generate_recommendation(
    article_number: int,
    article_title: str,
    coverage_percentage: float,
    missing_clauses: List[Dict[str, Any]],
    partially_covered_clauses: List[Dict[str, Any]],
    pdf_text: str = ""
) -> List[Dict[str, str]]:
    """
    Generate actionable recommendations for improving article coverage.
    
    Args:
        article_number: PDPL article number
        article_title: Title of the article
        coverage_percentage: Current coverage percentage (0-100)
        missing_clauses: List of missing clauses
        partially_covered_clauses: List of partially covered clauses
        pdf_text: Optional PDF text for context
        
    Returns:
        List of recommendation dictionaries, each with:
        - recommendation_number: int
        - pdpl_reference: str (e.g., "Article 11(1)(a)")
        - action: str
        - sample_policy_wording: str
    """
    if not model_manager.llm_enabled or not model_manager.openai_client:
        return "LLM not available for recommendations"
    
    try:
        # Extract relevant context from PDF for this article
        # Combine all clause texts to find relevant sections
        all_clause_texts = []
        if missing_clauses:
            for clause in missing_clauses:
                all_clause_texts.append(clause.get('text', ''))
        if partially_covered_clauses:
            for clause in partially_covered_clauses:
                all_clause_texts.append(clause.get('text', ''))
        
        # Use the first clause text or article title to extract relevant context
        search_text = all_clause_texts[0] if all_clause_texts else article_title
        
        # Extract relevant PDF sections (up to 3000 chars for better context)
        pdf_context = _extract_relevant_context(
            pdf_text=pdf_text,
            clause_text=search_text,
            max_size=3000
        ) if pdf_text else ""
        
        # Build context about gaps
        gaps_context = f"Article {article_number}: {article_title}\n"
        gaps_context += f"Current Coverage: {coverage_percentage:.0f}%\n\n"
        
        if missing_clauses:
            gaps_context += "MISSING CLAUSES:\n"
            for clause in missing_clauses[:3]:  # Top 3 missing
                label = clause.get('label', '')
                text = clause.get('text', '')[:200]
                explanation = clause.get('llm_explanation', '')
                gaps_context += f"- {label}: {text}...\n"
                if explanation:
                    gaps_context += f"  Reason: {explanation}\n"
        
        if partially_covered_clauses:
            gaps_context += "\nPARTIALLY COVERED CLAUSES:\n"
            for clause in partially_covered_clauses[:3]:  # Top 3 partial
                label = clause.get('label', '')
                text = clause.get('text', '')[:200]
                explanation = clause.get('llm_explanation', '')
                gaps_context += f"- {label}: {text}...\n"
                if explanation:
                    gaps_context += f"  Gap: {explanation}\n"
        
        prompt = f"""You are a PDPL compliance specialist. Based on the gaps listed below and the actual text from the user's uploaded privacy policy, produce targeted, corrective recommendations that reference specific sections from their document.

USER'S PRIVACY POLICY TEXT (Relevant Sections):
{pdf_context}

Gaps to address:
{gaps_context}

Requirements for each recommendation:
- Identify and quote specific text from the user's policy (shown above) that needs to be changed or is missing
- Describe concrete, implementable actions the organization must take to meet that requirement
- Provide suggested policy text that can replace or be added to the existing text
- Point out what specific text in their policy is problematic or missing
- Keep the recommendation clear, professional, and within 5–6 sentences

Task:
Generate 2–3 precise, actionable recommendations that:
1. Reference specific text from the user's uploaded policy document
2. Explain what needs to be changed, added, or clarified
3. Provide exact replacement or additional text
4. Connect each recommendation to the specific PDPL requirement

IMPORTANT: Return your response as a valid JSON object with a "recommendations" key containing an array. Each recommendation must be a JSON object with these exact fields:
- "recommendation_number": integer (1, 2, 3, etc.)
- "pdpl_reference": string (e.g., "Article 11")
- "current_policy_text": string (quote the specific text from the user's policy that needs changing, or "Not found" if missing)
- "action": string (the actionable steps, referencing the specific text that needs to change)
- "sample_policy_wording": string (suggested policy text that should replace or be added)

Example format:
{{
  "recommendations": [
    {{
      "recommendation_number": 1,
      "pdpl_reference": "Article 11",
      "current_policy_text": "We collect personal information from users.",
      "action": "The current text 'We collect personal information from users' is too vague. The organization should explicitly outline the methods and means of personal data collection, including specific channels like online forms, surveys, and third-party sources.",
      "sample_policy_wording": "We collect personal data through online forms, customer interactions, surveys, and third-party data sources to ensure that our data collection methods align with our operational needs and legal obligations."
    }},
    {{
      "recommendation_number": 2,
      "pdpl_reference": "Article 11",
      "current_policy_text": "Not found",
      "action": "The policy is missing a statement about the minimum necessary data principle. The organization must add a clear statement specifying that only data essential for the intended purpose will be collected.",
      "sample_policy_wording": "In adherence to the minimum necessary data principle, we commit to collecting only the personal data that is essential for fulfilling our specific purposes. Prior to any collection, we evaluate the necessity of the data to ensure compliance with legal standards."
    }}
  ]
}}

Return ONLY the JSON object, no additional text or markdown formatting."""

        response = model_manager.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a PDPL compliance expert providing actionable policy recommendations. Always return valid JSON arrays."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800,
            timeout=15,
            response_format={"type": "json_object"}
        )
        
        recommendation_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            import json
            # Try to parse as JSON object first (if wrapped)
            parsed = json.loads(recommendation_text)
            
            # If it's a dict with a 'recommendations' key, extract it
            if isinstance(parsed, dict):
                if 'recommendations' in parsed:
                    recommendations = parsed['recommendations']
                elif 'data' in parsed:
                    recommendations = parsed['data']
                else:
                    # Try to find any array in the dict
                    recommendations = next((v for v in parsed.values() if isinstance(v, list)), [])
            elif isinstance(parsed, list):
                recommendations = parsed
            else:
                recommendations = []
            
            # Validate and clean recommendations
            structured_recommendations = []
            for rec in recommendations:
                if isinstance(rec, dict):
                    structured_recommendations.append({
                        'recommendation_number': rec.get('recommendation_number', len(structured_recommendations) + 1),
                        'pdpl_reference': rec.get('pdpl_reference', ''),
                        'current_policy_text': rec.get('current_policy_text', 'Not found'),
                        'action': rec.get('action', ''),
                        'sample_policy_wording': rec.get('sample_policy_wording', '')
                    })
            
            return structured_recommendations if structured_recommendations else []
            
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse LLM recommendation as JSON: {e}")
            print(f"[WARNING] Raw response: {recommendation_text[:200]}")
            # Fallback: try to extract from markdown format
            return _parse_markdown_recommendations(recommendation_text)
        
    except Exception as e:
        print(f"[WARNING] LLM recommendation generation failed: {e}")
        return []


def _parse_markdown_recommendations(text: str) -> List[Dict[str, str]]:
    """
    Fallback parser for markdown-formatted recommendations.
    Parses text like:
    ### Recommendation 1: **PDPL Reference:** Article 11(1)(a) **Action:** ...
    """
    import re
    recommendations = []
    
    # Pattern to match recommendation blocks
    pattern = r'###\s*Recommendation\s*(\d+):\s*\*\*PDPL Reference:\*\*\s*([^\*]+?)\s*\*\*Action:\*\*\s*([^\*]+?)\s*\*\*Sample Policy Wording:\*\*\s*([^\-]+?)(?=---|###|$)'
    
    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        rec_num = int(match.group(1))
        pdpl_ref = match.group(2).strip()
        action = match.group(3).strip()
        sample = match.group(4).strip()
        
        recommendations.append({
            'recommendation_number': rec_num,
            'pdpl_reference': pdpl_ref,
            'current_policy_text': 'Not found',  # Can't extract from markdown easily
            'action': action,
            'sample_policy_wording': sample
        })
    
    return recommendations


def llm_rerank_articles(
    query_text: str, candidates: List[Dict[str, Any]], top_k: int = 20
) -> List[Dict[str, Any]]:
    """
    Use OpenAI API to re-rank articles based on legal relevance.

    Args:
        query_text: Query text from PDF
        candidates: List of candidate articles from previous retrieval
        top_k: Number of final results to return

    Returns:
        Re-ranked list of articles with LLM scores.
    """
    if not model_manager.llm_enabled or not model_manager.openai_client:
        return candidates[:top_k]

    if len(candidates) == 0:
        return []

    try:
        # Limit to top 50 candidates for LLM
        candidates_to_rank = candidates[: min(50, len(candidates))]

        # Build prompt for LLM ranking
        prompt = f"""You are a legal compliance expert. Rank these PDPL articles by relevance to the privacy policy query.

Query (Privacy Policy Content):
{query_text[:800]}

Articles to rank:
"""

        for i, cand in enumerate(candidates_to_rank, 1):
            article_text = cand["article"].get("text", "")[:200]
            article_num = cand["article"].get("article_number", "?")
            prompt += f"{i}. Article {article_num}: {article_text}...\n\n"

        prompt += """
Task: Score each article's relevance from 0-100.
You MUST return ONLY a single JSON array of numbers in order, with no extra text, no keys, and no explanation.

Example (format only): [95, 80, 60, 45]

Now return the scores array:"""

        response = model_manager.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a legal compliance expert."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,  # Increased for more variation
            max_tokens=100,
            timeout=10,
        )

        response_text = response.choices[0].message.content

        # Debug: show a snippet of raw LLM output
        print(f"[LLM RERANK RAW] {response_text[:200]}...")

        # Extract scores from response (robust parsing)
        scores = []
        json_str = None

        # First, try to extract a JSON array from between the first '[' and last ']'
        if "[" in response_text and "]" in response_text:
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            json_str = response_text[start:end]

        if json_str:
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    scores = [float(x) for x in parsed]
            except Exception as e:
                print(f"[WARN] Failed to parse LLM JSON scores: {e}")

        # Fallback: regex-extract numbers if JSON parse failed
        if not scores:
            import re as _re  # local alias to avoid any shadowing
            num_strings = _re.findall(r"\d+\.?\d*", response_text)
            try:
                scores = [float(x) for x in num_strings]
            except Exception as e:
                print(f"[WARN] Failed to parse numeric scores via regex: {e}")
                scores = []

        if not scores:
            print("[INFO] LLM re-ranking parse failed, using E5 ranking")
            return candidates[:top_k]

        # Apply LLM scores
        for i, cand in enumerate(candidates_to_rank):
            if i < len(scores):
                cand["llm_relevance_score"] = float(scores[i]) / 100.0
                e5_score = cand.get("e5_similarity", cand.get("similarity", 0.5))
                # final_score = 0.65×LLM_relevance + 0.35×E5_similarity
                cand["final_score"] = 0.7 * cand["llm_relevance_score"] + 0.3 * e5_score
            else:
                # If LLM did not return enough scores, fall back to pure E5 for remaining items
                cand["final_score"] = cand.get("e5_similarity", cand.get("similarity", 0))

        candidates_to_rank.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        remaining = candidates[len(candidates_to_rank):]
        for cand in remaining:
            cand["final_score"] = cand.get("e5_similarity", cand.get("similarity", 0))

        all_results = candidates_to_rank + remaining

        print(f"[OK] LLM re-ranked {len(candidates_to_rank)} articles")
        return all_results[:top_k]

    except Exception as e:
        print(f"[WARNING] LLM re-ranking failed: {e}")
        return candidates[:top_k]
