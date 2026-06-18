"""
Receptor Network - Foundation Layer

Core data structures for ghost storage:
- Slot: A named property of an entity
- Rule: Function that routes receptor activation by context
- Context: Coordinate set defining active/suppressed rules
- Delta: Record of receptor activation (not values)
- Receptor: Named binding point where rules and deltas interact
- Recipe: Template defining slots, receptors, and rules
- Entity: Node with recipe reference and delta chain
- ReceptorNetwork: Complete ghost storage system

No behavior yet—just structure.
Values are NOT stored. Only addresses (coordinates).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid


@dataclass
class Slot:
    """A named property of an entity (e.g., 'owner', 'status')."""
    name: str
    type_: str = "string"
    
    def __hash__(self):
        return hash(self.name)
    
    def __repr__(self):
        return f"Slot({self.name}: {self.type_})"


@dataclass
class Rule:
    """
    A function that routes receptor activation by context.
    
    Rules determine whether a delta propagates (activates) or stays dormant (gated)
    under a given context.
    
    Attributes:
        id: Unique identifier
        name: Human-readable name
        transmutation_fn: Function (delta, context) -> bool
        propagates_to: Contexts where this rule applies
        gates: Contexts where this rule is suppressed
        references: Other rule_ids this composes from
    """
    id: str
    name: str
    transmutation_fn: Callable[[Any, str], bool]
    propagates_to: List[str] = field(default_factory=list)
    gates: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    
    def applies_to_context(self, context_name: str) -> bool:
        """Does this rule activate under the given context?"""
        if context_name in self.gates:
            return False
        if not self.propagates_to:
            return True  # Applies to all contexts if no explicit list
        return context_name in self.propagates_to
    
    def should_activate_delta(self, delta: 'Delta', context_name: str) -> bool:
        """Determine if a delta should activate under this context."""
        if not self.applies_to_context(context_name):
            return False
        try:
            return self.transmutation_fn(delta, context_name)
        except Exception:
            return False
    
    def __repr__(self):
        return f"Rule({self.name})"


@dataclass
class Context:
    """
    A coordinate set defining which rules are active/suppressed.
    
    Context is not external input—it's itself a node in the receptor network.
    When you query with context_name, you activate a specific set of receptor pathways.
    
    Attributes:
        name: Context identifier
        active_rules: rule_ids that apply
        suppressed_rules: rule_ids that don't apply
        parent_context: Can derive from other contexts
        activation_timestamp: When this context was created/activated
        synthesis_path: Filled during traversal
    """
    name: str
    active_rules: List[str] = field(default_factory=list)
    suppressed_rules: List[str] = field(default_factory=list)
    parent_context: Optional[str] = None
    activation_timestamp: datetime = field(default_factory=datetime.now)
    synthesis_path: List[Dict[str, Any]] = field(default_factory=list)
    
    def __repr__(self):
        return f"Context({self.name})"


@dataclass
class Delta:
    """
    Record of receptor activation (NOT value storage).
    
    Delta stores:
    - Which receptors activated
    - Which rules applied
    - Which other deltas were referenced
    - Which gates blocked activation
    
    Delta does NOT store:
    - Computed values (ephemeral)
    - Explanations (synthesized on demand)
    
    Attributes:
        id: Unique identifier
        entity_id: Which entity this belongs to
        type_: Kind of delta (receptor_activation, receptor_gate, traversal, llm_synthesis)
        receptor_binding: The coordinates that activated
        references: Other delta_ids this bonds to
        is_gated_by: Gate delta_ids that suppress this
        synthesis_context: Context under which this was created
        source: Where this came from (user_input, api_call, llm_synthesis, system)
        timestamp: When this was created
        proof_hash: sha256 for verification
    """
    id: str
    entity_id: str
    type_: str  # receptor_activation | receptor_gate | traversal | llm_synthesis
    receptor_binding: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)
    is_gated_by: List[str] = field(default_factory=list)
    synthesis_context: Optional[str] = None
    source: str = "user_input"
    timestamp: datetime = field(default_factory=datetime.now)
    proof_hash: str = ""
    
    def is_gated_under_context(self, context_name: str) -> bool:
        """Is this delta gated (suppressed) under the given context?"""
        return len(self.is_gated_by) > 0
    
    def __hash__(self):
        return hash(self.id)
    
    def __repr__(self):
        return f"Delta({self.type_}:{self.id})"


@dataclass
class Receptor:
    """
    Named binding point where rules and deltas interact.
    
    Receptors are the addresses where relationships bind.
    They don't store values; they coordinate activation.
    
    Attributes:
        id: Unique identifier
        name: Human-readable name
        slot_ref: Which slot does this belong to?
        rule_refs: Which rules can activate this?
    """
    id: str
    name: str
    slot_ref: Optional[str] = None
    rule_refs: List[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"Receptor({self.name})"


@dataclass
class Recipe:
    """
    Template defining slots, receptors, and transmutation rules.
    
    Recipe is the blueprint that defines:
    - Which receptors exist
    - How they can bind
    - What rules route their activation
    
    Attributes:
        id: Unique identifier
        entity_type: What kind of entity uses this recipe (Property, Window, etc.)
        version: Recipe version (v1, v2, etc.)
        slots: List of named properties
        base_bindings: Initial values for slots
        receptors: Named binding points
        transmutation_rules: slot_name -> rule_id mapping
    """
    id: str
    entity_type: str
    version: str = "v1"
    slots: List[Slot] = field(default_factory=list)
    base_bindings: Dict[str, Any] = field(default_factory=dict)
    receptors: Dict[str, Receptor] = field(default_factory=dict)
    transmutation_rules: Dict[str, str] = field(default_factory=dict)
    
    def get_slot(self, slot_name: str) -> Optional[Slot]:
        """Get slot by name."""
        return next((s for s in self.slots if s.name == slot_name), None)
    
    def get_base_value(self, slot_name: str) -> Any:
        """Get base (genesis) value for a slot."""
        return self.base_bindings.get(slot_name)
    
    def __repr__(self):
        return f"Recipe({self.entity_type}:{self.version})"


@dataclass
class Entity:
    """
    Node in the receptor network with slots and deltas.
    
    Entity is NOT a container of values.
    Entity IS a node with references to recipes and a chain of deltas.
    Values are synthesized on query, not stored.
    
    Attributes:
        id: Unique identifier
        recipe_id: Which recipe defines this entity's structure
        recipe_version: Which version of the recipe
        delta_chain: Immutable list of delta_ids
        context_memory: Ephemeral, cleared between queries
        created_at: When entity was created
        updated_at: When last delta was appended
    """
    id: str
    recipe_id: str
    recipe_version: str = "v1"
    delta_chain: List[str] = field(default_factory=list)
    context_memory: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_delta(self, delta_id: str) -> None:
        """Append a delta to the immutable chain."""
        if delta_id not in self.delta_chain:
            self.delta_chain.append(delta_id)
            self.updated_at = datetime.now()
    
    def get_delta_chain(self) -> List[str]:
        """Get all deltas for this entity (immutable copy)."""
        return self.delta_chain.copy()
    
    def __repr__(self):
        return f"Entity({self.id})"


class ReceptorNetwork:
    """
    The complete ghost storage system.
    
    Stores:
    - Entities (nodes with recipes and delta chains)
    - Recipes (templates defining slots and rules)
    - Deltas (records of receptor activation)
    - Rules (functions that route activation)
    - Contexts (coordinate sets defining active rules)
    - Receptors (named binding points)
    
    This layer provides storage and basic CRUD.
    Synthesis happens in the TraversalEngine.
    """
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.recipes: Dict[str, Recipe] = {}
        self.deltas: Dict[str, Delta] = {}
        self.rules: Dict[str, Rule] = {}
        self.contexts: Dict[str, Context] = {}
        self.receptors: Dict[str, Receptor] = {}
    
    # ==================== Entity CRUD ====================
    
    def create_entity(self, entity_id: str, recipe_id: str, recipe_version: str = "v1") -> Entity:
        """Create a new entity with a recipe reference."""
        if entity_id in self.entities:
            raise ValueError(f"Entity {entity_id} already exists")
        
        entity = Entity(
            id=entity_id,
            recipe_id=recipe_id,
            recipe_version=recipe_version
        )
        self.entities[entity_id] = entity
        return entity
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Retrieve an entity by ID."""
        return self.entities.get(entity_id)
    
    def list_entities(self) -> List[Entity]:
        """List all entities."""
        return list(self.entities.values())
    
    # ==================== Recipe CRUD ====================
    
    def create_recipe(self, recipe_id: str, entity_type: str, version: str = "v1") -> Recipe:
        """Create a new recipe template."""
        if recipe_id in self.recipes:
            raise ValueError(f"Recipe {recipe_id} already exists")
        
        recipe = Recipe(id=recipe_id, entity_type=entity_type, version=version)
        self.recipes[recipe_id] = recipe
        return recipe
    
    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Retrieve a recipe by ID."""
        return self.recipes.get(recipe_id)
    
    def list_recipes(self) -> List[Recipe]:
        """List all recipes."""
        return list(self.recipes.values())
    
    def add_slot_to_recipe(self, recipe_id: str, slot_name: str, 
                          slot_type: str = "string", base_value: Any = None) -> Slot:
        """Add a slot to a recipe."""
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            raise ValueError(f"Recipe {recipe_id} not found")
        
        slot = Slot(name=slot_name, type_=slot_type)
        recipe.slots.append(slot)
        if base_value is not None:
            recipe.base_bindings[slot_name] = base_value
        
        return slot
    
    # ==================== Delta CRUD ====================
    
    def create_delta(self, entity_id: str, delta_type: str, 
                    receptor_binding: Dict[str, Any],
                    references: Optional[List[str]] = None,
                    synthesis_context: Optional[str] = None,
                    source: str = "user_input") -> Delta:
        """Create and store a delta (immutable append only)."""
        delta_id = str(uuid.uuid4())[:8]
        
        delta = Delta(
            id=delta_id,
            entity_id=entity_id,
            type_=delta_type,
            receptor_binding=receptor_binding,
            references=references or [],
            synthesis_context=synthesis_context,
            source=source
        )
        
        self.deltas[delta_id] = delta
        
        # Append to entity's delta chain
        entity = self.get_entity(entity_id)
        if entity:
            entity.add_delta(delta_id)
        
        return delta
    
    def get_delta(self, delta_id: str) -> Optional[Delta]:
        """Retrieve a delta by ID."""
        return self.deltas.get(delta_id)
    
    def list_deltas(self) -> List[Delta]:
        """List all deltas."""
        return list(self.deltas.values())
    
    def get_entity_delta_chain(self, entity_id: str) -> List[Delta]:
        """Get all deltas for an entity in order."""
        entity = self.get_entity(entity_id)
        if not entity:
            return []
        return [self.get_delta(did) for did in entity.get_delta_chain() if self.get_delta(did)]
    
    def create_gate(self, entity_id: str, gated_delta_id: str, 
                   suppressed_context: str, reason: str = "") -> Delta:
        """Create a gate delta (suppresses another delta without deletion)."""
        gate = Delta(
            id=str(uuid.uuid4())[:8],
            entity_id=entity_id,
            type_="receptor_gate",
            receptor_binding={
                "gated_delta": gated_delta_id,
                "context": suppressed_context,
                "reason": reason
            },
            source="system"
        )
        
        self.deltas[gate.id] = gate
        
        # Add gate to the gated delta's is_gated_by list
        gated = self.get_delta(gated_delta_id)
        if gated:
            gated.is_gated_by.append(gate.id)
        
        # Append gate to entity's chain
        entity = self.get_entity(entity_id)
        if entity:
            entity.add_delta(gate.id)
        
        return gate
    
    # ==================== Rule CRUD ====================
    
    def create_rule(self, rule_id: str, name: str, 
                   transmutation_fn: Callable[[Any, str], bool],
                   propagates_to: Optional[List[str]] = None,
                   gates: Optional[List[str]] = None) -> Rule:
        """Create a new rule for routing receptor activation."""
        if rule_id in self.rules:
            raise ValueError(f"Rule {rule_id} already exists")
        
        rule = Rule(
            id=rule_id,
            name=name,
            transmutation_fn=transmutation_fn,
            propagates_to=propagates_to or [],
            gates=gates or []
        )
        self.rules[rule_id] = rule
        return rule
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Retrieve a rule by ID."""
        return self.rules.get(rule_id)
    
    def list_rules(self) -> List[Rule]:
        """List all rules."""
        return list(self.rules.values())
    
    # ==================== Context CRUD ====================
    
    def create_context(self, context_name: str, 
                      active_rules: Optional[List[str]] = None,
                      suppressed_rules: Optional[List[str]] = None) -> Context:
        """Create a context coordinate."""
        context = Context(
            name=context_name,
            active_rules=active_rules or [],
            suppressed_rules=suppressed_rules or []
        )
        self.contexts[context_name] = context
        return context
    
    def get_context(self, context_name: str) -> Optional[Context]:
        """Retrieve a context by name."""
        return self.contexts.get(context_name)
    
    def list_contexts(self) -> List[Context]:
        """List all contexts."""
        return list(self.contexts.values())
    
    # ==================== Receptor CRUD ====================
    
    def create_receptor(self, receptor_id: str, name: str, slot_ref: Optional[str] = None) -> Receptor:
        """Create a named binding point."""
        receptor = Receptor(id=receptor_id, name=name, slot_ref=slot_ref)
        self.receptors[receptor_id] = receptor
        return receptor
    
    def get_receptor(self, receptor_id: str) -> Optional[Receptor]:
        """Retrieve a receptor by ID."""
        return self.receptors.get(receptor_id)
    
    def list_receptors(self) -> List[Receptor]:
        """List all receptors."""
        return list(self.receptors.values())
    
    # ==================== Stats ====================
    
    def stats(self) -> Dict[str, int]:
        """Get network statistics."""
        return {
            "entities": len(self.entities),
            "recipes": len(self.recipes),
            "deltas": len(self.deltas),
            "rules": len(self.rules),
            "contexts": len(self.contexts),
            "receptors": len(self.receptors)
        }
    
    def __repr__(self):
        stats = self.stats()
        return f"ReceptorNetwork({stats['entities']} entities, {stats['deltas']} deltas)"
