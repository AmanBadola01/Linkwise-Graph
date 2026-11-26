# PURPOSE: Entity Resolution service using RapidFuzz and contextual rules to merge aliases and rewire graph edges.
"""
Entity Resolution Service
-------------------------
Identifies and merges duplicate entities and alias variations into canonical nodes:
1. RapidFuzz Token-Set & Partial-Ratio string similarity (e.g. 'Acme Corp Technologies' == 'Acme Corp').
2. Person Initial Resolution (e.g. 'J. Smith' == 'John Smith', 'M. Lopez' == 'Maria Lopez').
3. Contextual / Synonym Matching (e.g. 'Auth Service' == 'Authentication Module' via text descriptions).
4. Edge Rewiring: Updates all relationships so source/target point to canonical node names.
5. Canonical Consolidation: Combines descriptions and records alias history for Neo4j.
"""

import re
import logging
from typing import List, Tuple, Dict, Set, Optional
from rapidfuzz import fuzz

# Import domain models
from backend.app.models.graph import (
    ExtractedEntity,
    ExtractedRelationship,
    GraphNode,
    GraphEdge,
)

logger = logging.getLogger("graphrag.resolver")


# CLASS: Resolves entity variations and aliases into canonical nodes and rewires relationship edges.
class EntityResolver:
    """
    Deduplicates entity variations using RapidFuzz and heuristic name resolution.
    """

    # FUNCTION: Initializes the EntityResolver with similarity thresholds and alias resolution rules.
    def __init__(self, similarity_threshold: float = 85.0):
        self.similarity_threshold = similarity_threshold
        # Optional dictionary for manual domain overrides (empty by default for document-agnostic operation)
        self.known_synonyms: Dict[str, str] = {}

    # FUNCTION: Main entry point that resolves entities into canonical nodes and updates edges.
    def resolve(
        self,
        clean_entities: List[ExtractedEntity],
        clean_relationships: List[ExtractedRelationship],
        source_doc: str = ""
    ) -> Tuple[List[GraphNode], List[GraphEdge], Dict[str, str]]:
        print(f"\n🔍 Running EntityResolver on {len(clean_entities)} clean entities...")

        # Step 1: Cluster entities that refer to the same concept
        alias_map, canonical_nodes = self._cluster_entities(clean_entities, source_doc)

        print(f"   • Consolidated {len(clean_entities)} entities into {len(canonical_nodes)} canonical nodes")

        # Step 2: Rewire all relationships to point to canonical entity names
        rewired_edges = self._rewire_relationships(clean_relationships, alias_map, source_doc)

        print(f"   • Rewired {len(clean_relationships)} relationships to canonical nodes ({len(rewired_edges)} unique edges)\n")

        return canonical_nodes, rewired_edges, alias_map

    # FUNCTION: Groups entities into alias clusters and constructs consolidated GraphNode instances.
    def _cluster_entities(
        self,
        entities: List[ExtractedEntity],
        source_doc: str
    ) -> Tuple[Dict[str, str], List[GraphNode]]:
        # alias_map maps lowercase raw entity name -> canonical display name
        alias_map: Dict[str, str] = {}
        # clusters: canonical_name -> list of ExtractedEntity objects
        clusters: Dict[str, List[ExtractedEntity]] = {}
        # Canonical names grouped by entity type. _are_same_entity never
        # merges across types, so only same-type clusters are ever compared —
        # previously every entity was fuzzy-compared against every cluster.
        clusters_by_type: Dict[str, List[str]] = {}

        # Sort entities so fuller, longer names are considered first as canonical candidates
        sorted_entities = sorted(entities, key=lambda e: len(e.name), reverse=True)

        for ent in sorted_entities:
            ent_lower = ent.name.lower().strip()

            # Check if this entity has already been mapped
            if ent_lower in alias_map:
                canonical_name = alias_map[ent_lower]
                clusters[canonical_name].append(ent)
                continue

            # Check if it matches an existing cluster (same type only)
            matched_canonical = None
            for canonical_name in clusters_by_type.get(ent.type.lower(), []):
                rep_entity = clusters[canonical_name][0]
                if self._are_same_entity(ent, rep_entity):
                    matched_canonical = canonical_name
                    break

            if matched_canonical:
                alias_map[ent_lower] = matched_canonical
                clusters[matched_canonical].append(ent)
            else:
                # Check known domain synonyms
                if ent_lower in self.known_synonyms:
                    target_canonical = self.known_synonyms[ent_lower]
                    alias_map[ent_lower] = target_canonical
                    if target_canonical not in clusters:
                        clusters[target_canonical] = []
                        clusters_by_type.setdefault(ent.type.lower(), []).append(target_canonical)
                    clusters[target_canonical].append(ent)
                else:
                    # New canonical entity
                    canonical_name = ent.name
                    alias_map[ent_lower] = canonical_name
                    clusters[canonical_name] = [ent]
                    clusters_by_type.setdefault(ent.type.lower(), []).append(canonical_name)

        # Build final canonical GraphNode objects with dynamically selected canonical name
        canonical_nodes: List[GraphNode] = []
        for cluster_key, items in clusters.items():
            best_canonical_name = self._select_canonical_name(items)
            node = self._merge_cluster_into_node(best_canonical_name, items, source_doc)
            canonical_nodes.append(node)
            # Ensure all items in this cluster map to the chosen canonical name
            for item in items:
                alias_map[item.name.lower()] = best_canonical_name
            alias_map[best_canonical_name.lower()] = best_canonical_name

        return alias_map, canonical_nodes

    # FUNCTION: Dynamically selects the most appropriate canonical name from a cluster of alias entities.
    def _select_canonical_name(self, items: List[ExtractedEntity]) -> str:
        """
        Selects the best canonical name for a cluster:
        1. For Persons: prefers full unabbreviated names ('John Smith' over 'J. Smith').
        2. For Products/Tech: checks if an item is an internal nickname/alias ('referred to internally as X').
        3. Tie-breaker: earliest page introduction and original occurrence.
        """
        if len(items) == 1:
            return items[0].name

        ent_type = items[0].type.strip().lower()

        # Rule 1: For Persons, avoid single-initial abbreviations
        if ent_type == "person":
            full_names = []
            for item in items:
                parts = item.name.replace(".", " ").split()
                if len(parts) >= 2 and len(parts[0]) > 1:
                    full_names.append(item)
            if full_names:
                return max(full_names, key=lambda x: len(x.name)).name

        # Rule 2: Detect alias/internal name phrasing in descriptions
        item_names = {item.name.lower(): item.name for item in items}
        demoted_names: Set[str] = set()

        for item in items:
            desc = item.description.lower()
            name_lower = item.name.lower()
            for cand_lower in item_names:
                if cand_lower == name_lower:
                    continue
                # If item description states it is an internal name for cand_lower
                if f"internal name for {cand_lower}" in desc:
                    demoted_names.add(name_lower)
                # If description states cand_lower is referred to internally as this item
                if f"referred to internally as {name_lower}" in desc or f"referred to internally as the {name_lower}" in desc:
                    demoted_names.add(name_lower)

        candidates = [item for item in items if item.name.lower() not in demoted_names]
        if candidates:
            # Prefer entity introduced earliest in document
            return min(candidates, key=lambda x: x.page_number).name

        return min(items, key=lambda x: x.page_number).name

    # FUNCTION: Evaluates whether two entities refer to the same real-world concept using RapidFuzz and rules.
    def _are_same_entity(self, e1: ExtractedEntity, e2: ExtractedEntity) -> bool:
        # Rule 1: Type compatibility (Never merge different types, e.g. Person vs Location)
        t1, t2 = e1.type.lower(), e2.type.lower()
        if t1 != t2:
            # Exception: Organization and Team can occasionally overlap, but keep strict for safety
            return False

        n1, n2 = e1.name.strip(), e2.name.strip()
        n1_lower, n2_lower = n1.lower(), n2.lower()

        # Rule 2: Exact lowercase match
        if n1_lower == n2_lower:
            return True

        # Rule 3: Known explicit synonyms
        if self.known_synonyms.get(n1_lower) == n2 or self.known_synonyms.get(n2_lower) == n1:
            return True

        # Rule 4: Person Initial Resolution (e.g. 'J. Smith' == 'John Smith', 'M. Lopez' == 'Maria Lopez')
        if t1 == "person":
            if self._matches_person_initial(n1, n2):
                return True

        # Rule 5: RapidFuzz Token-Set & Partial Ratio (catches 'Acme Corp Technologies' vs 'Acme Corp', '&' vs 'and')
        set_score = fuzz.token_set_ratio(n1_lower, n2_lower)
        partial_score = fuzz.partial_ratio(n1_lower, n2_lower)

        if set_score >= 90.0 or (partial_score >= 95.0 and len(n1) > 5 and len(n2) > 5):
            return True

        # Rule 6: Contextual / Description cross-reference (e.g. service abbreviation vs service full title)
        if self._is_referenced_in_description(e1, e2):
            return True

        return False

    # FUNCTION: Checks if two Person entities share the same surname and matching first initial.
    def _matches_person_initial(self, name1: str, name2: str) -> bool:
        # Example pairs: ('J. Smith', 'John Smith'), ('Maria Lopez', 'M. Lopez')
        parts1 = name1.replace(".", " ").split()
        parts2 = name2.replace(".", " ").split()

        if len(parts1) < 2 or len(parts2) < 2:
            return False

        last1, last2 = parts1[-1].lower(), parts2[-1].lower()
        if last1 != last2:
            return False

        first1, first2 = parts1[0].lower(), parts2[0].lower()
        # If one is a single initial and the other starts with that initial
        if len(first1) == 1 and first2.startswith(first1):
            return True
        if len(first2) == 1 and first1.startswith(first2):
            return True

        return False

    # FUNCTION: Checks if an entity description explicitly references another entity as an internal name or alias.
    def _is_referenced_in_description(self, e1: ExtractedEntity, e2: ExtractedEntity) -> bool:
        desc1 = e1.description.lower()
        desc2 = e2.description.lower()
        n1 = e1.name.lower()
        n2 = e2.name.lower()

        alias_indicators = (
            "referred to", "also known as", "internally as",
            "internal name", "code-named", "called", "alias"
        )

        # Check if text states alias: e.g. "referred to internally as the Payment Service"
        if n1 in desc2 and any(ind in desc2 for ind in alias_indicators):
            return True
        if n2 in desc1 and any(ind in desc1 for ind in alias_indicators):
            return True

        return False

    # FUNCTION: Merges a cluster of alias entities into a single canonical GraphNode.
    def _merge_cluster_into_node(
        self,
        canonical_name: str,
        items: List[ExtractedEntity],
        source_doc: str
    ) -> GraphNode:
        # Determine canonical type
        entity_type = items[0].type.strip().capitalize()

        # Collect unique aliases (names different from canonical_name)
        aliases = list({
            item.name for item in items
            if item.name.lower() != canonical_name.lower()
        })

        # Combine descriptions without repeating sentences
        descriptions = [item.description.strip() for item in items if item.description.strip()]
        merged_description = " ".join(dict.fromkeys(descriptions)) if descriptions else ""

        # Earliest page citation
        earliest_page = min(item.page_number for item in items)

        # Generate node ID
        node_id = self._generate_node_id(canonical_name)

        return GraphNode(
            id=node_id,
            name=canonical_name,
            type=entity_type,
            description=merged_description,
            source_doc=source_doc,
            page=earliest_page,
            degree=0,  # Will be populated after edges are rewired
            aliases=aliases,
            community_id=None
        )

    # FUNCTION: Rewires relationships so all source and target references point to canonical entity names.
    def _rewire_relationships(
        self,
        relationships: List[ExtractedRelationship],
        alias_map: Dict[str, str],
        source_doc: str
    ) -> List[GraphEdge]:
        rewired: List[GraphEdge] = []
        seen_edges: Set[Tuple[str, str, str]] = set()

        for rel in relationships:
            src_lower = rel.source.lower().strip()
            tgt_lower = rel.target.lower().strip()

            canonical_src = alias_map.get(src_lower, rel.source)
            canonical_tgt = alias_map.get(tgt_lower, rel.target)

            # Drop self-loops resulting from alias merges
            if canonical_src.lower() == canonical_tgt.lower():
                continue

            rel_type = rel.type.strip().upper().replace(" ", "_")
            edge_key = (canonical_src.lower(), rel_type, canonical_tgt.lower())

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)

            src_id = self._generate_node_id(canonical_src)
            tgt_id = self._generate_node_id(canonical_tgt)
            edge_id = f"e_{src_id}_{rel_type.lower()}_{tgt_id}"

            rewired.append(GraphEdge(
                id=edge_id,
                source=canonical_src,
                target=canonical_tgt,
                type=rel_type,
                description=rel.description,
                confidence=rel.confidence,
                source_doc=source_doc,
                page=rel.page_number
            ))

        return rewired

    # FUNCTION: Formats a canonical entity name into a sanitized node ID.
    def _generate_node_id(self, name: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
        sanitized = re.sub(r'_+', '_', sanitized).strip('_')
        return f"node_{sanitized}"

