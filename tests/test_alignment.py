"""
Tests for Alignment Layer

Verify:
- Coherence checks detect deviations
- Corrections are created without deletion
- Confidence scores reflect correction intensity
"""

import pytest
from core.receptor_network import ReceptorNetwork
from core.traversal_engine import TraversalEngine
from core.alignment_layer import AlignmentLayer, CoherenceCheckType


class TestAlignmentBasic:
    """Test coherence checking."""
    
    @pytest.fixture
    def setup(self):
        network = ReceptorNetwork()
        traversal = TraversalEngine(network)
        alignment = AlignmentLayer(network)
        
        recipe = network.create_recipe("prop_v1", "Property")
        network.add_slot_to_recipe("prop_v1", "status", base_value="clean")
        network.create_entity("Prop_1", "prop_v1")
        network.create_context("default")
        
        return {
            "network": network,
            "traversal": traversal,
            "alignment": alignment
        }
    
    def test_coherence_check_passes_on_clean_synthesis(self, setup):
        """Coherence should pass when synthesis is clean."""
        network = setup["network"]
        traversal = setup["traversal"]
        alignment = setup["alignment"]
        
        result = traversal.traverse("Prop_1", "default")
        report = alignment.verify_synthesis(
            "Prop_1",
            result.synthesis_delta_id,
            "default"
        )
        
        assert report.all_passed == True
        assert report.confidence == 1.0
    
    def test_coherence_check_detects_reference_error(self, setup):
        """Coherence should detect missing deltas."""
        network = setup["network"]
        alignment = setup["alignment"]
        
        # Manually create a synthesis delta with a bad reference
        bad_delta = network.create_delta(
            entity_id="Prop_1",
            delta_type="traversal",
            receptor_binding={
                "provenance": ["nonexistent_delta"],
                "values": {"status": "clean"}
            },
            synthesis_context="default",
            source="test"
        )
        
        report = alignment.verify_synthesis(
            "Prop_1",
            bad_delta.id,
            "default"
        )
        
        # Should detect the missing reference
        ref_check = next(
            (c for c in report.checks if c.check_type == CoherenceCheckType.REFERENCE_INTEGRITY),
            None
        )
        assert ref_check is not None
        assert ref_check.passed == False


class TestCorrectionDeltas:
    """Test creating correction deltas."""
    
    @pytest.fixture
    def setup(self):
        network = ReceptorNetwork()
        alignment = AlignmentLayer(network)
        
        recipe = network.create_recipe("prop_v1", "Property")
        network.add_slot_to_recipe("prop_v1", "status", base_value="unknown")
        network.create_entity("Prop_2", "prop_v1")
        
        return {"network": network, "alignment": alignment}
    
    def test_create_correction_delta(self, setup):
        """Correction deltas should not delete original."""
        network = setup["network"]
        alignment = setup["alignment"]
        
        # Create original delta
        original = network.create_delta(
            entity_id="Prop_2",
            delta_type="receptor_activation",
            receptor_binding={
                "slot_receptor": "status",
                "value": "clean"
            }
        )
        
        # Create correction
        correction = alignment.create_correction_delta(
            entity_id="Prop_2",
            original_delta_id=original.id,
            deviation="disputed_under_new_context",
            corrected_value="contested",
            context_name="new_context"
        )
        
        # Original should still exist
        assert network.get_delta(original.id) is not None
        
        # Correction should exist and reference original
        assert correction is not None
        assert original.id in correction.references
        
        # Both should be in chain
        entity = network.get_entity("Prop_2")
        chain = entity.get_delta_chain()
        assert original.id in chain
        assert correction.id in chain
    
    def test_correction_represents_splinter_truth(self, setup):
        """Correction delta should show it's a splinter, not a replacement."""
        network = setup["network"]
        alignment = setup["alignment"]
        
        original = network.create_delta(
            entity_id="Prop_2",
            delta_type="receptor_activation",
            receptor_binding={"slot_receptor": "status", "value": "clean"}
        )
        
        correction = alignment.create_correction_delta(
            entity_id="Prop_2",
            original_delta_id=original.id,
            deviation="context_change",
            corrected_value="contested",
            context_name="investigation"
        )
        
        # Correction should mark itself as such
        assert correction.receptor_binding["is_correction"] == True
        assert correction.receptor_binding["corrects_delta"] == original.id
        assert correction.source == "alignment_correction"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
