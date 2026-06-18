"""
Traversal Engine - The Query Loop

Executes synthesis: Load entity, recipe, context. For each slot, find active deltas.
Record path as new delta (proof of synthesis).

No expansion. No retrieval. Pure traversal.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from .receptor_network import ReceptorNetwork, Delta, Entity, Recipe, Context


@dataclass
class SynthesisPath:
    """Record of which receptors were traversed for one slot."""
    slot_name: str
    active_deltas: List[str] = field(default_factory=list)  # delta_ids that activated
    rules_applied: List[str] = field(default_factory=list)  # rule_ids consulted
    gates_checked: List[str] = field(default_factory=list)  # gate_ids evaluated
    final_value: Any = None  # synthesized value for this slot
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot": self.slot_name,
            "active_deltas": self.active_deltas,
            "rules_applied": self.rules_applied,
            "gates_checked": self.gates_checked,
            "value": self.final_value
        }


@dataclass
class TraversalResult:
    """Complete result of traversing an entity under a context."""
    entity_id: str
    context_name: str
    values: Dict[str, Any] = field(default_factory=dict)  # slot_name -> value
    paths: List[SynthesisPath] = field(default_factory=list)  # path per slot
    provenance: List[str] = field(default_factory=list)  # all delta_ids involved
    gates_applied: List[str] = field(default_factory=list)  # gates that suppressed
    synthesis_delta_id: Optional[str] = None  # proof this traversal happened
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "context": self.context_name,
            "values": self.values,
            "paths": [p.to_dict() for p in self.paths],
            "provenance": self.provenance,
            "gates_applied": self.gates_applied,
            "synthesis_delta_id": self.synthesis_delta_id,
            "timestamp": self.timestamp.isoformat()
        }


class TraversalEngine:
    """
    The query loop: traverse network, synthesize values, record path.
    
    Core algorithm:
    1. Load entity, recipe, context
    2. For each slot in recipe:
       a. Load base binding
       b. Load all deltas for this slot
       c. For each delta: check if rules allow it + not gated
       d. Get last ACTIVE delta = working truth
       e. Record path
    3. Store path as new delta (proof of synthesis)
    4. Return result
    """
    
    def __init__(self, network: ReceptorNetwork):
        self.network = network
    
    def traverse(self, entity_id: str, context_name: str) -> TraversalResult:
        """Execute the query loop: synthesize values under a context."""
        
        # Load coordinates
        entity = self.network.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        recipe = self.network.get_recipe(entity.recipe_id)
        if not recipe:
            raise ValueError(f"Recipe {entity.recipe_id} not found")
        
        context = self.network.get_context(context_name)
        if not context:
            # Create default context if missing
            context = self.network.create_context(context_name)
        
        # Traverse each slot
        result = TraversalResult(
            entity_id=entity_id,
            context_name=context_name,
            values={}
        )
        
        for slot in recipe.slots:
            path = self._traverse_slot(entity, recipe, slot.name, context)
            result.paths.append(path)
            result.values[slot.name] = path.final_value
            result.provenance.extend(path.active_deltas)
            result.gates_applied.extend(path.gates_checked)
        
        # Remove duplicates while preserving order
        result.provenance = list(dict.fromkeys(result.provenance))
        result.gates_applied = list(dict.fromkeys(result.gates_applied))
        
        # Store the traversal as a new delta (proof of synthesis)
        synthesis_delta = self._record_synthesis(entity, context, result)
        result.synthesis_delta_id = synthesis_delta.id
        
        return result
    
    def _traverse_slot(self, entity: Entity, recipe: Recipe, slot_name: str,
                       context: Context) -> SynthesisPath:
        """Traverse one slot: find active deltas, synthesize value."""
        
        path = SynthesisPath(slot_name=slot_name)
        
        # Start with base binding
        base_value = recipe.get_base_value(slot_name)
        path.final_value = base_value
        
        # Load all deltas for this entity
        all_deltas = self.network.get_entity_delta_chain(entity.id)
        
        # Filter deltas for this slot
        slot_deltas = [
            d for d in all_deltas
            if d.type_ == "receptor_activation"
            and d.receptor_binding.get("slot_receptor") == slot_name
        ]
        
        # For each delta, check if it should activate
        for delta in slot_deltas:
            # Check if gated under this context
            is_gated = self._is_delta_gated(delta, context)
            if is_gated:
                path.gates_checked.extend(delta.is_gated_by)
                continue
            
            # Check if rules allow it
            rule_id = delta.receptor_binding.get("rule_coordinate")
            rule_allows = self._rule_allows_delta(delta, rule_id, context)
            
            if rule_allows:
                path.active_deltas.append(delta.id)
                if rule_id:
                    path.rules_applied.append(rule_id)
                # Synthesize value from delta
                path.final_value = delta.receptor_binding.get("value", path.final_value)
        
        return path
    
    def _is_delta_gated(self, delta: Delta, context: Context) -> bool:
        """Check if delta is gated (suppressed) under this context."""
        if not delta.is_gated_by:
            return False
        
        for gate_id in delta.is_gated_by:
            gate = self.network.get_delta(gate_id)
            if gate and gate.type_ == "receptor_gate":
                gate_context = gate.receptor_binding.get("context")
                if gate_context == context.name:
                    return True
        
        return False
    
    def _rule_allows_delta(self, delta: Delta, rule_id: Optional[str],
                           context: Context) -> bool:
        """Check if a rule allows this delta to activate."""
        
        if not rule_id:
            return True  # No rule = always allow
        
        rule = self.network.get_rule(rule_id)
        if not rule:
            return False  # Rule doesn't exist = don't allow
        
        return rule.should_activate_delta(delta, context.name)
    
    def _record_synthesis(self, entity: Entity, context: Context,
                         result: TraversalResult) -> Delta:
        """Store the traversal as a new delta (proof of synthesis)."""
        
        synthesis_delta = self.network.create_delta(
            entity_id=entity.id,
            delta_type="traversal",
            receptor_binding={
                "context": context.name,
                "paths": [p.to_dict() for p in result.paths],
                "values": result.values,
                "provenance": result.provenance,
                "gates_applied": result.gates_applied
            },
            synthesis_context=context.name,
            source="traversal"
        )
        
        return synthesis_delta
    
    def compare_contexts(self, entity_id: str, context1: str, context2: str) -> Dict[str, Any]:
        """Query under two contexts and show splintered truths (where they differ)."""
        
        result1 = self.traverse(entity_id, context1)
        result2 = self.traverse(entity_id, context2)
        
        # Find splintered values
        splinters = {}
        for slot in set(list(result1.values.keys()) + list(result2.values.keys())):
            val1 = result1.values.get(slot)
            val2 = result2.values.get(slot)
            splinters[slot] = {
                context1: val1,
                context2: val2,
                "differs": val1 != val2
            }
        
        return {
            "entity_id": entity_id,
            "context1": context1,
            "context2": context2,
            "splinters": splinters,
            "active_deltas_c1": result1.provenance,
            "active_deltas_c2": result2.provenance,
            "gates_applied_c1": result1.gates_applied,
            "gates_applied_c2": result2.gates_applied
        }
