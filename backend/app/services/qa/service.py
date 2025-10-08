from typing import List, Dict, Any
from ..llm.friendly_client import FriendlyClient
from ..store.memory import MEM_STORE
import re
import hashlib
import time

class QAService:
    def __init__(self):
        self.llm_client = FriendlyClient()
        self.response_cache = {}  # Store recent responses to avoid duplicates
        self.cache_expiry = 300   # 5 minutes cache expiry
        self.conversation_history = {}  # Store conversation context per session
        self.max_context_messages = 10  # Keep last 10 messages for context
    
    def _clean_text(self, text: str) -> str:
        """Clean HTML tags and format text properly"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove special characters that might cause issues
        text = re.sub(r'[^\w\s.,!?;:()\-]', '', text)
        
        return text
    
    def _get_response_hash(self, question: str, context: str) -> str:
        """Generate hash for response caching"""
        content = f"{question.lower().strip()}{context[:500]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _add_to_conversation_history(self, session_id: str, question: str, answer: str):
        """Add question-answer pair to conversation history"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        self.conversation_history[session_id].append({
            "question": question,
            "answer": answer,
            "timestamp": time.time()
        })
        
        # Keep only last N messages
        if len(self.conversation_history[session_id]) > self.max_context_messages:
            self.conversation_history[session_id] = self.conversation_history[session_id][-self.max_context_messages:]
    
    def _get_conversation_context(self, session_id: str) -> str:
        """Get conversation context for building continuity"""
        if session_id not in self.conversation_history:
            return ""
        
        context_messages = []
        for msg in self.conversation_history[session_id][-5:]:  # Last 5 messages
            context_messages.append(f"Q: {msg['question']}\nA: {msg['answer'][:200]}...")
        
        return "\n\n".join(context_messages)
    
    def _is_duplicate_response(self, response: str, question_hash: str) -> bool:
        """Check if response is too similar to recent responses"""
        current_time = time.time()
        
        # Clean old cache entries
        self.response_cache = {
            k: v for k, v in self.response_cache.items() 
            if current_time - v['timestamp'] < self.cache_expiry
        }
        
        # Check for similar responses
        response_words = set(response.lower().split())
        
        for cached_hash, cached_data in self.response_cache.items():
            if cached_hash == question_hash:
                continue  # Skip exact same question
                
            cached_words = set(cached_data['response'].lower().split())
            similarity = len(response_words.intersection(cached_words)) / len(response_words.union(cached_words))
            
            if similarity > 0.8:  # 80% similarity threshold
                return True
        
        return False
    
    def _cache_response(self, question_hash: str, response: str):
        """Cache the response"""
        self.response_cache[question_hash] = {
            'response': response,
            'timestamp': time.time()
        }
    
    def _get_context_from_chunks(self, chunks: List[Dict[str, Any]], question: str) -> str:
        """Extract relevant context from document chunks"""
        if not chunks:
            return ""
        
        # Simple keyword-based relevance scoring
        question_words = set(question.lower().split())
        scored_chunks = []
        
        for chunk in chunks:
            text = self._clean_text(chunk.get('text', ''))
            title = self._clean_text(chunk.get('title', ''))
            
            # Score based on keyword overlap
            text_words = set(text.lower().split())
            title_words = set(title.lower().split())
            
            text_score = len(question_words.intersection(text_words))
            title_score = len(question_words.intersection(title_words)) * 2  # Weight title matches higher
            
            total_score = text_score + title_score
            
            if total_score > 0 or len(scored_chunks) < 3:  # Always include some context
                scored_chunks.append((total_score, chunk))
        
        # Sort by relevance and take top chunks
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:5]  # Top 5 most relevant chunks
        
        # Build context string
        context_parts = []
        for score, chunk in top_chunks:
            title = self._clean_text(chunk.get('title', ''))
            text = self._clean_text(chunk.get('text', ''))
            
            if title and text:
                context_parts.append(f"Section: {title}\nContent: {text}")
            elif text:
                context_parts.append(f"Content: {text}")
        
        return "\n\n".join(context_parts)
    
    def _get_persona_instructions(self, persona: str) -> str:
        """Get persona-specific analysis instructions"""
        persona_map = {
            "general": {
                "focus": "Provide balanced financial analysis covering key metrics, risks, and opportunities",
                "language": "professional yet accessible language suitable for general investors",
                "priorities": "revenue growth, profitability, competitive positioning, and risk factors"
            },
            "tech": {
                "focus": "Emphasize technology trends, digital transformation, R&D investments, and innovation metrics",
                "language": "tech-savvy terminology with focus on scalability and disruption potential",
                "priorities": "platform economics, network effects, technical moats, and digital market share"
            },
            "value": {
                "focus": "Deep dive into valuation metrics, asset quality, cash generation, and intrinsic value",
                "language": "Graham-and-Dodd style analysis with emphasis on fundamental strength",
                "priorities": "P/E ratios, book value, FCF yield, margin of safety, and quality metrics"
            },
            "growth": {
                "focus": "Analyze growth drivers, market expansion opportunities, and scalability potential",
                "language": "forward-looking analysis with emphasis on growth sustainability",
                "priorities": "revenue growth rates, market addressability, competitive advantages, and reinvestment"
            },
            "esg": {
                "focus": "Environmental, social, and governance factors alongside financial performance",
                "language": "sustainability-focused analysis with long-term perspective",
                "priorities": "ESG scores, carbon footprint, diversity metrics, and sustainable business practices"
            },
            "institutional": {
                "focus": "Comprehensive analysis suitable for large-scale investment decisions",
                "language": "detailed institutional-grade analysis with quantitative rigor",
                "priorities": "risk-adjusted returns, correlation analysis, portfolio fit, and liquidity considerations"
            },
            "retail": {
                "focus": "Clear, actionable insights suitable for individual investors",
                "language": "plain English explanations with practical investment implications",
                "priorities": "dividend yield, price volatility, entry points, and simple investment thesis"
            },
            "risk": {
                "focus": "Comprehensive risk assessment across operational, financial, and market dimensions",
                "language": "quantitative risk analysis with specific mitigation strategies",
                "priorities": "VaR metrics, stress scenarios, regulatory risks, and hedging strategies"
            }
        }
        
        persona_info = persona_map.get(persona, persona_map["general"])
        return f"""
PERSONA: {persona.title().replace('_', ' ')} Analysis Style

ANALYSIS FOCUS: {persona_info['focus']}
COMMUNICATION STYLE: Use {persona_info['language']}
KEY PRIORITIES: Focus on {persona_info['priorities']}
        """
    
    async def answer_question(self, doc_id: str, question: str, persona: str = "general") -> str:
        """Generate an answer to a question based on document content with conversation context and persona"""
        try:
            print(f"QA Service received question: '{question}' for doc_id: {doc_id}")
            
            # Check if this is a casual/greeting message - let the AI handle it naturally
            question_lower = question.lower().strip()
            if question_lower in ['hi', 'hello', 'hey'] and len(question.strip()) <= 5:
                print(f"Detected simple greeting: '{question}', letting AI handle naturally...")
                # Don't return early - let the AI respond naturally to greetings
            
            # Get document chunks from memory store
            chunks = MEM_STORE.get(doc_id)
            if not chunks:
                return "I couldn't find the document. Please make sure it was uploaded successfully."
            
            # Extract relevant context
            context = self._get_context_from_chunks(chunks, question)
            
            if not context.strip():
                return "I couldn't find relevant information in the document to answer your question."
            
            # Add randomness and timestamp to prevent caching
            import time
            import random
            timestamp = int(time.time())
            random_seed = random.randint(1000, 9999)
            
            # Build conversation history context
            conversation_context = ""
            if hasattr(self, 'conversation_history') and self.conversation_history:
                recent_history = list(self.conversation_history.items())[-3:]  # Last 3 exchanges
                if recent_history:
                    conversation_context = "\n\nRECENT CONVERSATION CONTEXT:\n"
                    for i, (prev_q, prev_a) in enumerate(recent_history):
                        conversation_context += f"{i+1}. Q: {prev_q[:100]}...\n   A: {prev_a[:150]}...\n"
            
            # Get persona-specific instructions
            persona_instructions = self._get_persona_instructions(persona)
            
            # Enhanced system prompt with conversation awareness and persona-based analysis
            system_prompt = f"""You are an expert financial analysis AI with deep knowledge of:
- Financial markets, regulations, and compliance (SEC, FINRA, Basel III, Dodd-Frank)
- Corporate finance, valuation methods, and risk assessment
- International accounting standards (GAAP, IFRS)
- Investment strategies and portfolio management
- Regulatory environments across major markets
- Economic indicators and market analysis

Session: {random_seed} | Time: {timestamp} | Mode: Persona-Based Analysis

{persona_instructions}

CONVERSATION GUIDELINES:
1. If the user says simple greetings like "Hi", "Hello", respond warmly and briefly mention you can help analyze the document
2. For specific questions about document content, provide detailed financial analysis TAILORED to the selected persona
3. NEVER repeat previous responses - always provide fresh perspectives
4. Build on conversation history when relevant
5. Combine document analysis with your extensive financial knowledge
6. Provide actionable, specific insights with quantitative details when possible
7. ALWAYS analyze and communicate in the style specified by the persona above

RESPONSE APPROACH:
- Greetings: Keep it brief and friendly, mention document analysis capabilities
- Questions: Detailed analysis with headers, bullet points, numbers, percentages - all tailored to persona style
- Always match response length and complexity to the question asked and persona expectations{conversation_context}"""
            
            # Detect question complexity to choose appropriate response style
            is_simple_greeting = len(question.strip()) <= 10 and any(word in question_lower for word in ['hi', 'hello', 'hey', 'thanks'])
            is_simple_question = len(question.strip()) <= 20
            
            # Enhanced prompt variations - adjust complexity based on question type
            if is_simple_greeting:
                prompt_variations = [
                    f"Simple greeting: '{question}'\n\nDocument context: {context[:200]}...\n\nProvide a brief, friendly response mentioning you can help analyze this document.",
                    f"User said: '{question}'\n\nAvailable document: {context[:200]}...\n\nGive a warm, concise greeting and offer to help with document analysis."
                ]
            elif is_simple_question:
                prompt_variations = [
                    f"Question: {question}\n\nDocument content: {context}\n\nProvide a focused, direct answer based on the document.",
                    f"User asks: {question}\n\nSource material: {context}\n\nGive a clear, concise response with key insights."
                ]
            else:
                prompt_variations = [
                f"📊 FINANCIAL ANALYSIS REQUEST #{random_seed}\n\nQuestion: {question}\n\n📋 DOCUMENT EVIDENCE:\n{context}\n\n🎯 ANALYSIS REQUIREMENTS:\n- Apply current market conditions and regulatory environment (2024)\n- Integrate financial theory and best practices\n- Provide quantitative insights with specific metrics\n- Consider industry benchmarks and peer comparisons\n- Format response with clear headers and actionable recommendations",
                
                f"🔍 REGULATORY COMPLIANCE REVIEW {timestamp}\n\nInquiry: {question}\n\n📚 SOURCE MATERIAL:\n{context}\n\n⚖️ COMPLIANCE FRAMEWORK:\n- Apply SEC, FINRA, and relevant regulatory guidelines\n- Consider recent regulatory updates and enforcement trends\n- Assess compliance risks and mitigation strategies\n- Provide structured recommendations with timeline\n- Include relevant regulatory citations when applicable",
                
                f"💼 STRATEGIC ASSESSMENT #{random_seed}-{timestamp}\n\nBusiness Question: {question}\n\n📊 INFORMATION BASE:\n{context}\n\n🚀 STRATEGIC ANALYSIS:\n- Apply Porter's Five Forces and competitive analysis\n- Consider current economic indicators and market trends\n- Integrate valuation methodologies (DCF, multiples, etc.)\n- Assess growth potential and market positioning\n- Provide scenario analysis and risk-adjusted projections",
                
                f"🎯 RISK EVALUATION SESSION {timestamp}\n\nRisk Inquiry: {question}\n\n🛡️ DATA FOUNDATION:\n{context}\n\n📈 RISK ASSESSMENT PROTOCOL:\n- Apply VaR, stress testing, and sensitivity analysis concepts\n- Consider market, credit, operational, and regulatory risks\n- Integrate current volatility and market conditions\n- Provide risk mitigation recommendations\n- Include quantitative risk metrics when possible",
                
                f"💰 INVESTMENT ANALYSIS #{random_seed}\n\nInvestment Question: {question}\n\n💹 RESEARCH BASE:\n{context}\n\n📊 INVESTMENT FRAMEWORK:\n- Apply modern portfolio theory and asset allocation principles\n- Consider current yield curves and market valuations\n- Integrate ESG factors and sustainable finance principles\n- Assess liquidity, duration, and credit considerations\n- Provide specific investment recommendations with rationale",
                
                f"🏢 CORPORATE FINANCE REVIEW {timestamp}-{random_seed}\n\nCorporate Query: {question}\n\n🔢 FINANCIAL DATA:\n{context}\n\n💼 CORPORATE ANALYSIS:\n- Apply capital structure optimization and cost of capital concepts\n- Consider dividend policy and capital allocation strategies\n- Integrate M&A analysis and corporate governance principles\n- Assess financial performance vs. industry benchmarks\n- Provide strategic financial recommendations",
                
                f"📱 MARKET INTELLIGENCE BRIEF #{timestamp}\n\nMarket Question: {question}\n\n🌐 INTELLIGENCE SOURCE:\n{context}\n\n📈 MARKET ANALYSIS:\n- Apply technical and fundamental analysis principles\n- Consider current market sentiment and macroeconomic factors\n- Integrate sector rotation and cyclical analysis\n- Assess supply/demand dynamics and price discovery\n- Provide market outlook with specific price targets",
                
                f"🎪 COMPREHENSIVE DUE DILIGENCE {random_seed}-{timestamp}\n\nDD Question: {question}\n\n🔬 INVESTIGATION MATERIAL:\n{context}\n\n🔍 DUE DILIGENCE FRAMEWORK:\n- Apply comprehensive financial, legal, and operational analysis\n- Consider stakeholder impact and regulatory approval processes\n- Integrate competitive positioning and market share analysis\n- Assess synergies, integration risks, and value creation potential\n- Provide go/no-go recommendation with detailed rationale"
            ]
            
            user_prompt = random.choice(prompt_variations)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Enhanced temperature and parameters for maximum response variety
            temperature = round(random.uniform(0.6, 1.0), 2)  # Wider range
            top_p = round(random.uniform(0.75, 0.98), 2)  # More variation
            freq_penalty = round(random.uniform(0.3, 0.7), 2)  # Variable penalty
            pres_penalty = round(random.uniform(0.2, 0.6), 2)  # Variable penalty
            
            payload = {
                "model": self.llm_client.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": random.randint(1500, 2500),  # Vary response length
                "top_p": top_p,
                "frequency_penalty": freq_penalty,
                "presence_penalty": pres_penalty,
                "seed": random_seed,
                "n": 1,  # Ensure single completion
                "stream": False  # Ensure no streaming
            }
            
            # Make direct API call with varied parameters
            import httpx
            url = f"{self.llm_client.base_url}/v1/chat/completions"
            
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    url,
                    headers=self.llm_client.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("choices") and len(data["choices"]) > 0:
                        answer = data["choices"][0]["message"]["content"].strip()
                        
                        # Check for duplicate responses and retry if needed
                        question_hash = self._get_response_hash(question, context)
                        
                        # If response is too similar to recent ones, try again with different parameters
                        if self._is_duplicate_response(answer, question_hash):
                            print(f"Duplicate response detected, retrying with higher variation...")
                            
                            # Retry with maximum variation
                            retry_payload = {
                                "model": self.llm_client.model,
                                "messages": messages,
                                "temperature": 1.0,  # Maximum creativity
                                "max_tokens": 2000,
                                "top_p": 0.95,
                                "frequency_penalty": 0.8,  # Strong repetition penalty
                                "presence_penalty": 0.7,   # Strong new topic encouragement
                                "seed": random.randint(10000, 99999)  # New random seed
                            }
                            
                            retry_response = await client.post(
                                url,
                                headers=self.llm_client.headers,
                                json=retry_payload
                            )
                            
                            if retry_response.status_code == 200:
                                retry_data = retry_response.json()
                                if retry_data.get("choices") and len(retry_data["choices"]) > 0:
                                    answer = retry_data["choices"][0]["message"]["content"].strip()
                        
                        # Cache the response and add to conversation history
                        self._cache_response(question_hash, answer)
                        
                        # Update conversation history
                        if not hasattr(self, 'conversation_history'):
                            self.conversation_history = {}
                        self.conversation_history[question] = answer
                        
                        # Keep only last 10 exchanges to prevent memory bloat
                        if len(self.conversation_history) > 10:
                            oldest_key = list(self.conversation_history.keys())[0]
                            del self.conversation_history[oldest_key]
                        
                        return answer
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
                    return "I'm having trouble generating a response. Please try rephrasing your question."
                
        except Exception as e:
            print(f"QA Service error: {e}")
            return f"I encountered an error while processing your question: {str(e)}"

    async def answer_multi_document_question(self, doc_ids: List[str], question: str, persona: str = "general") -> str:
        """Generate an answer based on multiple documents with persona-based analysis"""
        try:
            print(f"Multi-doc QA Service received: '{question}' for {len(doc_ids)} documents")
            
            # Let AI handle greetings naturally rather than hardcoding responses
            question_lower = question.lower().strip()
            if question_lower in ['hi', 'hello', 'hey'] and len(question.strip()) <= 5:
                print(f"Detected simple greeting in multi-doc mode, letting AI handle naturally...")
            
            # Collect all relevant chunks from all documents
            all_chunks = []
            doc_titles = []
            
            for doc_id in doc_ids:
                chunks = MEM_STORE.get(doc_id)
                if chunks:
                    all_chunks.extend(chunks)
                    # Get document title from first chunk
                    if chunks and chunks[0].get('source'):
                        doc_titles.append(chunks[0]['source'])
            
            if not all_chunks:
                return "I couldn't find any of the specified documents."
            
            # Extract relevant context from all documents
            context = self._get_context_from_chunks(all_chunks, question)
            
            if not context.strip():
                return "I couldn't find relevant information across your documents to answer your question."
            
            # Add anti-caching mechanisms
            import time
            import random
            timestamp = int(time.time())
            random_seed = random.randint(1000, 9999)
            
            # Build conversation history context for multi-document analysis
            conversation_context = ""
            if hasattr(self, 'conversation_history') and self.conversation_history:
                recent_history = list(self.conversation_history.items())[-3:]  # Last 3 exchanges
                if recent_history:
                    conversation_context = "\n\nRECENT CONVERSATION CONTEXT:\n"
                    for i, (prev_q, prev_a) in enumerate(recent_history):
                        conversation_context += f"{i+1}. Q: {prev_q[:100]}...\n   A: {prev_a[:150]}...\n"

            # Get persona-specific instructions for multi-document analysis
            persona_instructions = self._get_persona_instructions(persona)
            
            # Enhanced system prompt for multi-document analysis with persona and conversation handling
            system_prompt = f"""You are a senior financial analyst and portfolio strategist with expertise in:
- Cross-document financial analysis and due diligence
- Comparative company analysis and peer benchmarking
- Portfolio construction and risk management
- Regulatory compliance across multiple jurisdictions
- M&A analysis and corporate finance
- Market analysis and economic research
- Investment strategy and asset allocation

Session: MD-{random_seed} | Time: {timestamp} | Analysis Type: Multi-Document Persona-Based Synthesis

{persona_instructions}

CONVERSATION GUIDELINES:
1. If user says simple greetings like "Hi", "Hello", respond briefly and mention you can analyze multiple documents
2. For complex questions, provide detailed multi-document synthesis TAILORED to the selected persona
3. NEVER repeat previous analyses - create fresh perspectives each time
4. Match response complexity to question complexity AND persona expectations
5. Build on conversation history when relevant
6. ALWAYS analyze and communicate in the style specified by the persona above

RESPONSE APPROACH:
- Greetings: Brief, friendly, mention multi-document capabilities in persona style
- Complex questions: Full analysis with cross-document insights, patterns, and recommendations - all tailored to persona
- Always provide value appropriate to the question asked and persona requirements{conversation_context}"""
            
            # Detect question complexity for multi-document analysis
            is_simple_greeting = len(question.strip()) <= 10 and any(word in question.lower() for word in ['hi', 'hello', 'hey', 'thanks'])
            is_simple_question = len(question.strip()) <= 20
            
            # Enhanced multi-document analysis prompts - adjust based on complexity
            if is_simple_greeting:
                analysis_approaches = [
                    f"User greeting: '{question}'\n\nMulti-document context: {len(doc_ids)} documents available\nSample content: {context[:200]}...\n\nProvide a brief, friendly response mentioning your multi-document analysis capabilities.",
                    f"Simple greeting: '{question}'\n\nDocument portfolio: {len(doc_ids)} files loaded\nContent preview: {context[:200]}...\n\nGive a warm, concise greeting and offer multi-document analysis help."
                ]
            elif is_simple_question:
                analysis_approaches = [
                    f"Question: {question}\n\nMulti-document content: {context}\n\nProvide a focused answer drawing insights from multiple documents.",
                    f"User asks: {question}\n\nCross-document data: {context}\n\nGive a clear, direct response with key insights from the document set."
                ]
            else:
                analysis_approaches = [
                f"📈 PORTFOLIO ANALYSIS MATRIX #{random_seed}\n\nMulti-Company Question: {question}\n\n📊 DOCUMENT UNIVERSE:\nSources: {', '.join(doc_titles[:3])}\nData Points: {len(all_chunks)} sections\n\n🎯 CONSOLIDATED INTELLIGENCE:\n{context}\n\n💼 ANALYSIS FRAMEWORK:\n- Apply comparative valuation (P/E, EV/EBITDA, P/B ratios)\n- Cross-reference financial metrics and performance indicators\n- Identify industry leaders and laggards with quantitative support\n- Provide portfolio allocation recommendations with risk-adjusted returns\n- Structure response: Executive Summary → Company Comparisons → Portfolio Strategy",
                
                f"🔍 CROSS-DOCUMENT DUE DILIGENCE {timestamp}\n\nInvestigation: {question}\n\n📋 RESEARCH DATABASE:\nDocument Portfolio: {len(doc_ids)} companies/assets\nAnalytical Depth: {len(all_chunks)} data segments\n\n🛡️ INTEGRATED EVIDENCE BASE:\n{context}\n\n⚖️ DUE DILIGENCE PROTOCOL:\n- Apply comprehensive risk assessment framework (market, credit, operational, regulatory)\n- Cross-validate financial statements and key metrics\n- Identify red flags and positive catalysts across documents\n- Provide investment thesis with specific entry/exit criteria\n- Include scenario analysis with probability-weighted outcomes",
                
                f"🏢 COMPARATIVE INDUSTRY ANALYSIS #{random_seed}-{timestamp}\n\nSector Question: {question}\n\n🌐 INDUSTRY INTELLIGENCE:\nCompany Set: {', '.join(doc_titles[:4])}...\nAnalytical Scope: {len(all_chunks)} information blocks\n\n📊 SECTOR DATABASE:\n{context}\n\n🚀 INDUSTRY ANALYSIS FRAMEWORK:\n- Apply Porter's Five Forces across the competitive landscape\n- Benchmark key performance metrics vs. industry averages\n- Identify sector trends, disruption risks, and growth drivers\n- Rank companies by competitive positioning and financial strength\n- Provide sector allocation strategy with overweight/underweight recommendations",
                
                f"💰 MULTI-ASSET VALUATION STUDY {timestamp}\n\nValuation Inquiry: {question}\n\n🔢 FINANCIAL DATA REPOSITORY:\nAsset Universe: {len(doc_ids)} investment opportunities\nValuation Inputs: {len(all_chunks)} financial data points\n\n💹 CONSOLIDATED FINANCIALS:\n{context}\n\n📈 VALUATION METHODOLOGY:\n- Apply multiple valuation approaches (DCF, comparables, precedent transactions)\n- Cross-reference assumptions and validate financial projections\n- Identify value creation opportunities and potential synergies\n- Provide fair value estimates with confidence intervals\n- Rank opportunities by risk-adjusted return potential",
                
                f"🎯 STRATEGIC M&A ANALYSIS #{random_seed}\n\nM&A Question: {question}\n\n🤝 TRANSACTION DATABASE:\nTarget/Acquirer Universe: {', '.join(doc_titles[:3])}\nStrategic Intelligence: {len(all_chunks)} analysis points\n\n⚡ STRATEGIC CONTEXT:\n{context}\n\n🔄 M&A EVALUATION FRAMEWORK:\n- Apply strategic fit analysis and synergy quantification\n- Cross-analyze financial capacity and integration complexity\n- Assess regulatory approval probability and competitive response\n- Model accretion/dilution scenarios with sensitivity analysis\n- Provide strategic recommendation with optimal deal structure",
                
                f"📱 ESG & SUSTAINABILITY SCORECARD {timestamp}-{random_seed}\n\nESG Question: {question}\n\n🌱 SUSTAINABILITY DATABASE:\nCompany Portfolio: {len(doc_ids)} ESG profiles\nSustainability Metrics: {len(all_chunks)} ESG data points\n\n🌍 ESG INTELLIGENCE BASE:\n{context}\n\n♻️ ESG ANALYSIS FRAMEWORK:\n- Apply comprehensive ESG scoring methodology\n- Cross-reference sustainability commitments with actual performance\n- Identify ESG leaders and improvement opportunities\n- Assess regulatory compliance and reputational risks\n- Provide ESG-integrated investment recommendations with impact measurement",
                
                f"📊 MACROECONOMIC IMPACT ASSESSMENT #{timestamp}\n\nMacro Question: {question}\n\n🌐 ECONOMIC EXPOSURE ANALYSIS:\nCompany/Asset Set: {', '.join(doc_titles[:3])}\nEconomic Sensitivity Data: {len(all_chunks)} exposure points\n\n📈 MACRO-FINANCIAL LINKAGES:\n{context}\n\n🔮 MACROECONOMIC FRAMEWORK:\n- Apply interest rate, inflation, and currency sensitivity analysis\n- Cross-reference geographic and sector exposures\n- Model recession/expansion scenarios across the portfolio\n- Assess central bank policy impact and market cycle positioning\n- Provide defensive/growth allocation strategy based on economic outlook",
                
                f"🚀 GROWTH & INNOVATION PORTFOLIO {random_seed}-{timestamp}\n\nGrowth Question: {question}\n\n💡 INNOVATION ECOSYSTEM:\nGrowth Companies: {len(doc_ids)} innovation leaders\nGrowth Catalysts: {len(all_chunks)} opportunity vectors\n\n⚡ GROWTH INTELLIGENCE:\n{context}\n\n🎪 GROWTH INVESTMENT FRAMEWORK:\n- Apply growth metrics analysis (revenue growth, market expansion, R&D efficiency)\n- Cross-validate growth strategies and execution capabilities\n- Identify disruptive technologies and market share expansion opportunities\n- Assess scalability and competitive moats\n- Provide growth-focused portfolio construction with risk management overlay"
            ]
            
            user_prompt = random.choice(analysis_approaches)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Enhanced parameters for multi-document analysis with maximum variation
            temperature = round(random.uniform(0.5, 0.95), 2)
            top_p = round(random.uniform(0.8, 0.98), 2)
            freq_penalty = round(random.uniform(0.4, 0.8), 2)
            pres_penalty = round(random.uniform(0.3, 0.7), 2)
            
            payload = {
                "model": self.llm_client.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": random.randint(2000, 3000),  # Vary response length
                "top_p": top_p,
                "frequency_penalty": freq_penalty,
                "presence_penalty": pres_penalty,
                "seed": random_seed,
                "n": 1,
                "stream": False
            }
            
            # Make direct API call
            import httpx
            url = f"{self.llm_client.base_url}/v1/chat/completions"
            
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    url,
                    headers=self.llm_client.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("choices") and len(data["choices"]) > 0:
                        answer = data["choices"][0]["message"]["content"].strip()
                        
                        # Check for duplicate responses in multi-document context
                        multi_doc_context = f"multi_docs_{len(doc_ids)}_{question}"
                        question_hash = self._get_response_hash(question, multi_doc_context)
                        
                        # Retry if response is too similar to previous multi-document responses
                        if self._is_duplicate_response(answer, question_hash):
                            print(f"Duplicate multi-document response detected, retrying...")
                            
                            # Use different approach and maximum variation for retry
                            retry_prompt = random.choice(analysis_approaches)
                            retry_messages = [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": retry_prompt}
                            ]
                            
                            retry_payload = {
                                "model": self.llm_client.model,
                                "messages": retry_messages,
                                "temperature": 1.0,  # Maximum creativity
                                "max_tokens": 2800,
                                "top_p": 0.95,
                                "frequency_penalty": 0.9,  # Maximum repetition penalty
                                "presence_penalty": 0.8,   # Strong new topic encouragement
                                "seed": random.randint(50000, 99999)  # Very different seed
                            }
                            
                            retry_response = await client.post(
                                url,
                                headers=self.llm_client.headers,
                                json=retry_payload
                            )
                            
                            if retry_response.status_code == 200:
                                retry_data = retry_response.json()
                                if retry_data.get("choices") and len(retry_data["choices"]) > 0:
                                    answer = retry_data["choices"][0]["message"]["content"].strip()
                        
                        # Cache the multi-document response and update conversation history
                        self._cache_response(question_hash, answer)
                        
                        # Update conversation history for multi-document queries
                        if not hasattr(self, 'conversation_history'):
                            self.conversation_history = {}
                        
                        # Add special prefix for multi-document questions
                        multi_doc_question = f"[Multi-Doc] {question}"
                        self.conversation_history[multi_doc_question] = answer
                        
                        # Keep only last 10 exchanges to prevent memory bloat
                        if len(self.conversation_history) > 10:
                            oldest_key = list(self.conversation_history.keys())[0]
                            del self.conversation_history[oldest_key]
                        
                        return answer
                else:
                    print(f"Multi-doc API Error: {response.status_code} - {response.text}")
                    return "I'm having trouble generating a response for your multi-document query."
                
        except Exception as e:
            print(f"Multi-document QA Service error: {e}")
            return f"I encountered an error while processing your multi-document question: {str(e)}"

# Singleton instance
qa_service = QAService()