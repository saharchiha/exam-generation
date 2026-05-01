import logging
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import weaviate
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

load_dotenv()

logger = logging.getLogger(__name__)


class WeaviateRetriever:
    """
    Weaviate-based retriever using REAL semantic search with your embeddings
    """

    def __init__(self, weaviate_url: str = "http://localhost:8080", class_name: str = "ExamChunk"):
        self.weaviate_url = weaviate_url
        self.class_name = class_name
        self.client = self._initialize_weaviate_client()
        self.embedder = self._initialize_embedder()

        logger.info(f"WeaviateRetriever initialized with semantic search on class '{self.class_name}'")

    def _initialize_weaviate_client(self):
        """Initialize Weaviate client"""
        try:
            client = weaviate.Client(
                url=self.weaviate_url,
                timeout_config=(5, 30)
            )

            schema = client.schema.get()
            logger.info(f"Connected to Weaviate. Found {len(schema.get('classes', []))} classes")
            return client

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            raise

    def _initialize_embedder(self):
        """Initialize your actual embedder"""
        try:
            from embeddings.embedder import MiniLMEmbedder
            embedder = MiniLMEmbedder()
            logger.info("✅ Successfully loaded MiniLMEmbedder")
            return embedder
        except ImportError as e:
            logger.error(f"❌ Failed to import MiniLMEmbedder: {e}")
            raise

    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate REAL embedding using your embedder"""
        try:
            embedding = self.embedder.embed_single_query(query)
            logger.info(f"Generated REAL embedding of length: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Error generating real embedding: {e}")
            raise

    def semantic_search(self,
                        query_embedding: List[float],
                        class_name: str = None,
                        limit: int = 10,
                        certainty_threshold: float = 0.1,
                        filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Perform REAL semantic search with PROGRESSIVE filter relaxation
        """
        if class_name is None:
            class_name = self.class_name

        try:
            # Get all available properties dynamically
            schema = self.client.schema.get(class_name)
            available_props = [prop['name'] for prop in schema.get('properties', [])]

            logger.info(f"🔍 Searching in class '{class_name}' with properties: {available_props}")

            # PROGRESSIVE FILTERING STRATEGY
            # Try multiple filter combinations from most specific to least specific
            filter_strategies = self._build_filter_strategies(filters)

            results = []
            for strategy_name, where_filter in filter_strategies:
                logger.info(f"🎯 Trying filter strategy: {strategy_name}")

                query = self.client.query.get(
                    class_name,
                    available_props
                ).with_additional(["distance", "id", "certainty"])

                # Add filters if provided
                if where_filter:
                    query = query.with_where(where_filter)

                # Vector search with your REAL embeddings
                query = query.with_near_vector({
                    "vector": query_embedding,
                    "certainty": certainty_threshold
                }).with_limit(limit)

                result = query.do()

                # Check if we got results
                if result and "data" in result and "Get" in result["data"]:
                    items = result["data"]["Get"].get(class_name, None)

                    if items and len(items) > 0:
                        logger.info(f"✅ Strategy '{strategy_name}' found {len(items)} results")
                        results = self._process_items(items, available_props)
                        break  # Stop on first successful strategy
                    else:
                        logger.info(f"⚠️ Strategy '{strategy_name}' found 0 results, trying next...")
                else:
                    logger.warning(f"Strategy '{strategy_name}' returned invalid result")

            if not results:
                logger.warning(f"❌ All filter strategies failed, returning empty results")
                return []

            # Sort by certainty (higher is better)
            results.sort(key=lambda x: x.get("certainty", 0), reverse=True)
            logger.info(f"✅ Semantic search completed: {len(results)} relevant documents found")

            # Log top results for debugging
            if results:
                logger.info(
                    f"📊 Top result - Certainty: {results[0].get('certainty', 0):.3f}, Subject: {results[0].get('subject', 'N/A')}")

            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _build_filter_strategies(self, filters: Dict[str, Any]) -> List[tuple]:
        """
        Build multiple filter strategies from most to least specific
        Returns list of (strategy_name, where_filter) tuples
        """
        strategies = []

        if not filters:
            return [("no_filters", None)]

        # Clean filters - remove None, empty, and "mixed" values
        clean_filters = {k: v for k, v in filters.items()
                         if v and v != "mixed" and str(v).strip()}

        if not clean_filters:
            return [("no_filters", None)]

        # Strategy 1: All filters
        if len(clean_filters) >= 2:
            strategies.append(("all_filters", self._build_where_filter(clean_filters)))

        # Strategy 2: Subject + Language only (most important)
        subject_lang = {}
        if "subject" in clean_filters:
            subject_lang["subject"] = clean_filters["subject"]
        if "language" in clean_filters:
            subject_lang["language"] = clean_filters["language"]
        if subject_lang and subject_lang not in [s[1] for s in strategies]:
            strategies.append(("subject_language", self._build_where_filter(subject_lang)))

        # Strategy 3: Subject only
        if "subject" in clean_filters:
            strategies.append(("subject_only", self._build_where_filter({"subject": clean_filters["subject"]})))

        # Strategy 4: Language only
        if "language" in clean_filters:
            strategies.append(("language_only", self._build_where_filter({"language": clean_filters["language"]})))

        # Strategy 5: No filters (semantic search only)
        strategies.append(("no_filters", None))

        return strategies

    def _process_items(self, items: List[Dict], available_props: List[str]) -> List[Dict]:
        """Process retrieved items into standardized format"""
        results = []

        for item in items:
            # Dynamically extract all properties
            doc_data = {
                "content": item.get("text", item.get("content", item.get("clean_text", ""))),
                "distance": item["_additional"].get("distance", 0),
                "certainty": item["_additional"].get("certainty", 0),
                "id": item["_additional"]["id"],
                "search_type": "semantic"
            }

            # Add all other properties dynamically
            for prop in available_props:
                if prop not in ["clean_text", "text", "content"]:
                    doc_data[prop] = item.get(prop, "")

            results.append(doc_data)

        return results

    def _build_where_filter(self, filters: Dict[str, Any]) -> Optional[Dict]:
        """Build Weaviate WHERE filter from filter dictionary"""
        if not filters:
            return None

        conditions = []

        for key, value in filters.items():
            if value and value != "mixed":  # Skip empty or "mixed" values
                conditions.append({
                    "path": [key],
                    "operator": "Equal",
                    "valueText": str(value)
                })

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        # Multiple conditions - use AND
        return {
            "operator": "And",
            "operands": conditions
        }

    def count_documents(self, class_name: str = None) -> int:
        """Count total documents"""
        if class_name is None:
            class_name = self.class_name

        try:
            result = self.client.query.aggregate(class_name).with_meta_count().do()
            if "data" in result and "Aggregate" in result["data"]:
                count = result["data"]["Aggregate"][class_name][0]["meta"]["count"]
                logger.info(f"📊 Total documents in '{class_name}': {count}")
                return count
            return 0
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0


class SemanticRetriever:
    """
    Main retriever focused on semantic search with your embeddings
    """

    def __init__(self, weaviate_retriever: WeaviateRetriever = None, class_name: str = "ExamChunk"):
        self.weaviate_retriever = weaviate_retriever or WeaviateRetriever(class_name=class_name)
        logger.info(f"SemanticRetriever initialized with real embeddings on class '{class_name}'")

    def retrieve(self,
                 query: str,
                 search_type: str = "semantic",
                 language: str = "french",
                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main retrieval using REAL semantic search with progressive filter relaxation
        """
        try:
            # Step 1: Generate REAL embedding using your model
            logger.info(f"🔍 Generating embedding for: '{query}'")
            query_embedding = self.weaviate_retriever.generate_query_embedding(query)

            # Step 2: Perform semantic search with progressive filtering
            retrieval_results = self.weaviate_retriever.semantic_search(
                query_embedding,
                limit=10,
                certainty_threshold=0.3,  # Lower threshold for better recall
                filters=filters
            )

            # Step 3: Enhance and filter results
            enhanced_results = self._enhance_results(retrieval_results, query)

            # Step 4: Prepare response
            response = {
                "query": query,
                "language": language,
                "search_type": search_type,
                "filters_applied": filters or {},
                "embedding_dimensions": len(query_embedding),
                "retrieved_documents": enhanced_results,
                "retrieval_count": len(enhanced_results),
                "total_documents": self.weaviate_retriever.count_documents(),
                "success": len(enhanced_results) > 0
            }

            logger.info(f"✅ Retrieved {len(enhanced_results)} documents")

            # Log subject distribution
            subjects = {}
            for doc in enhanced_results[:5]:
                subj = doc.get('subject', 'Unknown')
                subjects[subj] = subjects.get(subj, 0) + 1
            logger.info(f"📚 Top subjects: {subjects}")

            return response

        except Exception as e:
            logger.error(f"❌ Error in semantic retrieval: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_response(query, language)

    def _enhance_results(self, results: List[Dict], query: str) -> List[Dict]:
        """Enhance results with better scoring and filtering"""
        if not results:
            return []

        # Filter out very low-certainty results (but be more lenient)
        filtered_results = [r for r in results if r.get("certainty", 0) > 0.25]

        # Enhance with relevance scoring
        for result in filtered_results:
            certainty = result.get("certainty", 0)
            distance = result.get("distance", 0)

            # Convert to similarity score (higher is better)
            similarity_score = 1.0 / (1.0 + distance) if distance > 0 else 1.0

            # Use certainty if available, otherwise use similarity
            relevance_score = certainty if certainty > 0 else similarity_score

            result["relevance_score"] = round(relevance_score, 3)
            result["similarity_score"] = round(similarity_score, 3)

        # Sort by relevance
        filtered_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        return filtered_results[:10]

    def _fallback_response(self, query: str, language: str) -> Dict[str, Any]:
        """Fallback response"""
        return {
            "query": query,
            "language": language,
            "retrieved_documents": [],
            "retrieval_count": 0,
            "success": False,
            "error": "Semantic search failed - check your embedder"
        }