"""
Tests for Traversal Engine

Verify:
- Basic traversal works
- Values are synthesized correctly
- Paths are recorded as deltas
- Splinters are visible when contexts differ
"""

import pytest
from core.receptor_network import ReceptorNetwork
from core.traversal_engine import TraversalEngine


class TestTraversalBasic:
    """Test basic traversal algorithm."""
    
    @pytest.fixture
    def setup(self):
        """Set up a simple window recipe and entity."""
        network = ReceptorNetwork()
        traversal = TraversalEngine(network)
        
        # Create recipe
        recipe = network.create_recipe("window_v1", "Window")
        network.add_slot_to_recipe("window_v1", "state", base_value="closed")
        network.add_slot_to_recipe("window_v1", "material", base_value="wood")
        
        # Create entity
        network.create_entity("Window_1", "window_v1")
        
        # Create contexts
        network.create_context("default")
        network.create_context("painted_shut")
        
        return {"network": network, "traversal": traversal}
    
    def test_traverse_returns_base_values(self, setup):
        """When no deltas exist, return base bindings."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        result = traversal.traverse("Window_1", "default")
        
        assert result.entity_id == "Window_1"
        assert result.context_name == "default"
        assert result.values["state"] == "closed"
        assert result.values["material"] == "wood"
    
    def test_traverse_appends_synthesis_delta(self, setup):
        """Traversal should create a proof delta."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        result = traversal.traverse("Window_1", "default")
        
        # Result should have synthesis_delta_id
        assert result.synthesis_delta_id is not None
        
        # That delta should exist in the network
        synthesis_delta = network.get_delta(result.synthesis_delta_id)
        assert synthesis_delta is not None
        assert synthesis_delta.type_ == "traversal"
    
    def test_traverse_with_active_delta(self, setup):
        """When delta exists, return its value."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        # Create a delta
        network.create_delta(
            entity_id="Window_1",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "state",
                "value": "open",
                "rule_coordinate": "default_rule"
            }
        )
        
        result = traversal.traverse("Window_1", "default")
        
        # Value should be from delta, not base
        assert result.values["state"] == "open"
    
    def test_traverse_records_path(self, setup):
        """Path should show which deltas were active."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        delta1 = network.create_delta(
            entity_id="Window_1",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "state",
                "value": "stuck",
                "rule_coordinate": "painted_rule"
            }
        )
        
        result = traversal.traverse("Window_1", "default")
        
        # Path should exist for state slot
        state_path = next((p for p in result.paths if p.slot_name == "state"), None)
        assert state_path is not None
        assert delta1.id in state_path.active_deltas


class TestTraversalWithGates:
    """Test traversal respects gating."""
    
    @pytest.fixture
    def setup(self):
        network = ReceptorNetwork()
        traversal = TraversalEngine(network)
        
        recipe = network.create_recipe("prop_v1", "Property")
        network.add_slot_to_recipe("prop_v1", "owner", base_value="Unknown")
        network.create_entity("Prop_1", "prop_v1")
        
        network.create_context("context_a")
        network.create_context("context_b")
        
        return {"network": network, "traversal": traversal}
    
    def test_gated_delta_suppressed_under_context(self, setup):
        """Gated deltas should not activate under their gate context."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        # Create delta
        delta1 = network.create_delta(
            entity_id="Prop_1",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "owner",
                "value": "Alice"
            }
        )
        
        # Gate it under context_b
        gate = network.create_gate(
            entity_id="Prop_1",
            gated_delta_id=delta1.id,
            suppressed_context="context_b"
        )
        
        # Query under context_a: delta should be active
        result_a = traversal.traverse("Prop_1", "context_a")
        assert result_a.values["owner"] == "Alice"
        
        # Query under context_b: delta should be suppressed, return base
        result_b = traversal.traverse("Prop_1", "context_b")
        assert result_b.values["owner"] == "Unknown"
    
    def test_gated_delta_not_deleted(self, setup):
        """Gated deltas should still be in the chain."""
        network = setup["network"]
        
        delta1 = network.create_delta(
            entity_id="Prop_1",
            delta_type="receptor_activation",
            receptor_binding={"slot_receptor": "owner", "value": "Alice"}
        )
        
        gate = network.create_gate(
            entity_id="Prop_1",
            gated_delta_id=delta1.id,
            suppressed_context="context_b"
        )
        
        # Both should be in chain
        entity = network.get_entity("Prop_1")
        chain = entity.get_delta_chain()
        
        assert delta1.id in chain
        assert gate.id in chain


class TestTraversalSplinters:
    """Test comparing contexts reveals splinters."""
    
    @pytest.fixture
    def setup(self):
        network = ReceptorNetwork()
        traversal = TraversalEngine(network)
        
        recipe = network.create_recipe("btc_v1", "UTXO")
        network.add_slot_to_recipe("btc_v1", "status", base_value="unknown")
        network.create_entity("TX_1", "btc_v1")
        
        network.create_context("fatf_2020")
        network.create_context("user_report")
        
        return {"network": network, "traversal": traversal}
    
    def test_compare_contexts_shows_splinters(self, setup):
        """Querying under two contexts should show where values differ."""
        network = setup["network"]
        traversal = setup["traversal"]
        
        # Create delta for fatf context
        network.create_delta(
            entity_id="TX_1",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "status",
                "value": "clean",
                "synthesis_context": "fatf_2020"
            }
        )
        
        # Create delta for user_report context
        network.create_delta(
            entity_id="TX_1",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "status",
                "value": "tainted",
                "synthesis_context": "user_report"
            }
        )
        
        comparison = traversal.compare_contexts("TX_1", "fatf_2020", "user_report")
        
        assert comparison["entity_id"] == "TX_1"
        assert comparison["splinters"]["status"]["differs"] == True
        assert comparison["splinters"]["status"]["fatf_2020"] == "clean"
        assert comparison["splinters"]["status"]["user_report"] == "tainted"
