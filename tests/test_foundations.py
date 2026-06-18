"""
Test Phase 1a - Foundation Layer

Verify that the core data structures work correctly:
- Creation and retrieval
- Immutability of delta chains
- Proper linkage between components

No traversal or synthesis yet—just structure.
"""

import pytest
from core.receptor_network import (
    ReceptorNetwork,
    Slot,
    Rule,
    Context,
    Delta,
    Receptor,
    Recipe,
    Entity
)


class TestSlot:
    """Test Slot data structure."""
    
    def test_slot_creation(self):
        slot = Slot(name="owner", type_="string")
        assert slot.name == "owner"
        assert slot.type_ == "string"
    
    def test_slot_hashable(self):
        slot1 = Slot(name="owner")
        slot2 = Slot(name="owner")
        # Same name should have same hash
        assert hash(slot1) == hash(slot2)


class TestRule:
    """Test Rule data structure."""
    
    def test_rule_creation(self):
        def dummy_fn(delta, context):
            return True
        
        rule = Rule(
            id="rule_1",
            name="Always propagate",
            transmutation_fn=dummy_fn,
            propagates_to=["context_1", "context_2"]
        )
        
        assert rule.id == "rule_1"
        assert rule.name == "Always propagate"
        assert "context_1" in rule.propagates_to
    
    def test_rule_applies_to_context(self):
        def dummy_fn(delta, context):
            return True
        
        rule = Rule(
            id="rule_1",
            name="Test",
            transmutation_fn=dummy_fn,
            propagates_to=["context_1"]
        )
        
        assert rule.applies_to_context("context_1") == True
        assert rule.applies_to_context("context_2") == False
    
    def test_rule_gating(self):
        def dummy_fn(delta, context):
            return True
        
        rule = Rule(
            id="rule_1",
            name="Test",
            transmutation_fn=dummy_fn,
            propagates_to=["context_1"],
            gates=["context_1"]  # Gated under context_1
        )
        
        assert rule.applies_to_context("context_1") == False  # Gated


class TestContext:
    """Test Context data structure."""
    
    def test_context_creation(self):
        context = Context(
            name="FATF_2020",
            active_rules=["rule_1", "rule_2"]
        )
        
        assert context.name == "FATF_2020"
        assert "rule_1" in context.active_rules


class TestDelta:
    """Test Delta data structure."""
    
    def test_delta_creation(self):
        delta = Delta(
            id="delta_1",
            entity_id="entity_1",
            type_="receptor_activation",
            receptor_binding={"slot": "owner", "value": "Alice"}
        )
        
        assert delta.id == "delta_1"
        assert delta.type_ == "receptor_activation"
        assert delta.receptor_binding["value"] == "Alice"
    
    def test_delta_references(self):
        delta = Delta(
            id="delta_2",
            entity_id="entity_1",
            type_="receptor_activation",
            receptor_binding={},
            references=["delta_1"]
        )
        
        assert "delta_1" in delta.references
    
    def test_delta_gating(self):
        delta = Delta(
            id="delta_1",
            entity_id="entity_1",
            type_="receptor_activation",
            receptor_binding={},
            is_gated_by=["gate_1"]
        )
        
        assert len(delta.is_gated_by) > 0


class TestRecipe:
    """Test Recipe data structure."""
    
    def test_recipe_creation(self):
        recipe = Recipe(
            id="recipe_1",
            entity_type="Property",
            version="v1"
        )
        
        assert recipe.entity_type == "Property"
        assert recipe.version == "v1"
    
    def test_recipe_add_slot(self):
        recipe = Recipe(
            id="recipe_1",
            entity_type="Property",
            version="v1"
        )
        
        slot = Slot(name="owner", type_="string")
        recipe.slots.append(slot)
        recipe.base_bindings["owner"] = "Unknown"
        
        assert recipe.get_slot("owner") is not None
        assert recipe.get_base_value("owner") == "Unknown"


class TestEntity:
    """Test Entity data structure."""
    
    def test_entity_creation(self):
        entity = Entity(
            id="entity_1",
            recipe_id="recipe_1",
            recipe_version="v1"
        )
        
        assert entity.id == "entity_1"
        assert entity.recipe_id == "recipe_1"
    
    def test_entity_delta_chain_append(self):
        entity = Entity(
            id="entity_1",
            recipe_id="recipe_1"
        )
        
        entity.add_delta("delta_1")
        entity.add_delta("delta_2")
        
        chain = entity.get_delta_chain()
        assert len(chain) == 2
        assert "delta_1" in chain
        assert "delta_2" in chain
    
    def test_entity_delta_chain_immutable(self):
        """Verify that delta chain copy is immutable (can't modify original)."""
        entity = Entity(
            id="entity_1",
            recipe_id="recipe_1"
        )
        
        entity.add_delta("delta_1")
        chain = entity.get_delta_chain()
        chain.append("delta_2")  # Modify the copy
        
        # Original should be unchanged
        assert len(entity.get_delta_chain()) == 1


class TestReceptorNetwork:
    """Test the complete ReceptorNetwork."""
    
    @pytest.fixture
    def network(self):
        """Create a fresh network for each test."""
        return ReceptorNetwork()
    
    def test_network_creation(self, network):
        assert network.stats() == {
            "entities": 0,
            "recipes": 0,
            "deltas": 0,
            "rules": 0,
            "contexts": 0,
            "receptors": 0
        }
    
    def test_recipe_creation_and_retrieval(self, network):
        recipe = network.create_recipe("prop_v1", "Property", version="v1")
        
        assert recipe is not None
        assert network.get_recipe("prop_v1") == recipe
    
    def test_recipe_duplicate_error(self, network):
        network.create_recipe("prop_v1", "Property")
        
        with pytest.raises(ValueError):
            network.create_recipe("prop_v1", "Property")  # Duplicate
    
    def test_add_slot_to_recipe(self, network):
        recipe = network.create_recipe("prop_v1", "Property")
        slot = network.add_slot_to_recipe("prop_v1", "owner", base_value="Unknown")
        
        assert slot.name == "owner"
        assert recipe.get_slot("owner") == slot
        assert recipe.get_base_value("owner") == "Unknown"
    
    def test_entity_creation_and_retrieval(self, network):
        network.create_recipe("prop_v1", "Property")
        entity = network.create_entity("entity_1", "prop_v1")
        
        assert entity is not None
        assert network.get_entity("entity_1") == entity
    
    def test_entity_duplicate_error(self, network):
        network.create_recipe("prop_v1", "Property")
        network.create_entity("entity_1", "prop_v1")
        
        with pytest.raises(ValueError):
            network.create_entity("entity_1", "prop_v1")  # Duplicate
    
    def test_delta_creation_and_append(self, network):
        network.create_recipe("prop_v1", "Property")
        network.create_entity("entity_1", "prop_v1")
        
        delta = network.create_delta(
            entity_id="entity_1",
            delta_type="receptor_activation",
            receptor_binding={"slot": "owner", "value": "Alice"}
        )
        
        assert delta is not None
        assert network.get_delta(delta.id) == delta
        
        # Delta should be in entity's chain
        entity = network.get_entity("entity_1")
        assert delta.id in entity.get_delta_chain()
    
    def test_delta_chain_immutability(self, network):
        """Verify deltas are appended, not replaced."""
        network.create_recipe("prop_v1", "Property")
        network.create_entity("entity_1", "prop_v1")
        
        delta1 = network.create_delta(
            entity_id="entity_1",
            delta_type="receptor_activation",
            receptor_binding={"value": "Alice"}
        )
        
        delta2 = network.create_delta(
            entity_id="entity_1",
            delta_type="receptor_activation",
            receptor_binding={"value": "Bob"}
        )
        
        entity = network.get_entity("entity_1")
        chain = entity.get_delta_chain()
        
        # Both deltas should be in the chain
        assert len(chain) == 2
        assert delta1.id in chain
        assert delta2.id in chain
    
    def test_gate_creation(self, network):
        """Test creating a gate (suppress delta without deletion)."""
        network.create_recipe("prop_v1", "Property")
        network.create_entity("entity_1", "prop_v1")
        
        delta1 = network.create_delta(
            entity_id="entity_1",
            delta_type="receptor_activation",
            receptor_binding={"value": "Alice"}
        )
        
        gate = network.create_gate(
            entity_id="entity_1",
            gated_delta_id=delta1.id,
            suppressed_context="new_context",
            reason="disputed"
        )
        
        # Gate should be created
        assert gate is not None
        assert gate.type_ == "receptor_gate"
        
        # Original delta should still exist
        assert network.get_delta(delta1.id) is not None
        
        # Original delta should know it's gated
        assert gate.id in delta1.is_gated_by
        
        # Both should be in the chain
        entity = network.get_entity("entity_1")
        chain = entity.get_delta_chain()
        assert delta1.id in chain
        assert gate.id in chain
    
    def test_rule_creation_and_retrieval(self, network):
        def dummy_fn(delta, context):
            return True
        
        rule = network.create_rule(
            "rule_1",
            "Test rule",
            dummy_fn,
            propagates_to=["context_1"]
        )
        
        assert rule is not None
        assert network.get_rule("rule_1") == rule
    
    def test_context_creation_and_retrieval(self, network):
        context = network.create_context("FATF_2020", active_rules=["rule_1"])
        
        assert context is not None
        assert network.get_context("FATF_2020") == context
    
    def test_network_stats(self, network):
        """Verify stats are correctly counted."""
        network.create_recipe("prop_v1", "Property")
        network.create_entity("entity_1", "prop_v1")
        network.create_delta(
            entity_id="entity_1",
            delta_type="receptor_activation",
            receptor_binding={}
        )
        
        stats = network.stats()
        assert stats["recipes"] == 1
        assert stats["entities"] == 1
        assert stats["deltas"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
