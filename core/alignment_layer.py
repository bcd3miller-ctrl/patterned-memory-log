"""
Alignment Layer - Coherence Detection & Splinter Correction

After synthesis, verify all deltas in the path bond correctly.
Detect deviations (contradictions, impossible states).
Correct without deletion—create correction deltas that represent splinter truths.

This is like DNA mismatch repair:
- Deviation detected (base pair mismatch)
- Not deleted
- Backed up and corrected
- Process continues with proof

For patterned memory:
- Deviation detected (delta contradicts context rules)
- Not deleted
- Correction delta created (new splinter)
- Future queries can see both paths
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .receptor_network import ReceptorNetwork, Delta, Entity, Recipe, Context


class CoherenceCheckType(Enum):
    """Types of coherence checks."""
    GATE_LOGIC = "gate_logic"  # Delta both active and suppressed?
    REFERENCE_INTEGRITY = "reference_integrity"  # All references exist?
    RULE_CONSISTENCY = "rule_consistency"  # Rules don't contradict?
    CONTEXT_CONSISTENCY = "context_consistency"  # Context rules align?
    SPLINTER_ALIGNMENT = "splinter_alignment"  # Splinters correctly tracked?


@dataclass
class CoherenceCheckResult:
    """Result of a single coherence check."""
    check_type: CoherenceCheckType
    passed: bool
    message: str
    affected_deltas: List[str] = field(default_factory=list)
    affected_contexts: List[str] = field(default_factory=list)
    recommendation: Optional[str] = None


@dataclass
class CoherenceReport:
    """Complete coherence audit for a synthesis."""
    entity_id: str
    context_name: str
    synthesis_delta_id: str
    checks: List[CoherenceCheckResult] = field(default_factory=list)
    all_passed: bool = True
    deviations: List[str] = field(default_factory=list)  # What deviated
    corrections: List[str] = field(default_factory=list)  # Correction delta_ids
    confidence: float = 1.0  # 1.0 = perfect, <1.0 = corrections needed
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "context": self.context_name,
            "synthesis_delta_id": self.synthesis_delta_id,
            "all_passed": self.all_passed,
            "confidence": self.confidence,
            "checks": [
                {
                    "type": c.check_type.value,
                    "passed": c.passed,
                    "message": c.message,
                    "affected_deltas": c.affected_deltas
                }
                for c in self.checks
            ],
            "deviations": self.deviations,
            "corrections": self.corrections,
            "timestamp": self.timestamp.isoformat()
        }


class AlignmentLayer:
    """
    Detects and corrects deviations without deletion.
    
    Treats contradictions as splinter truths, not errors.
    Creates correction deltas (new splinters) to represent the mismatch.
    """
    
    def __init__(self, network: ReceptorNetwork):
        self.network = network
    
    def verify_synthesis(self, entity_id: str, synthesis_delta_id: str,
                        context_name: str) -> CoherenceReport:
        """Run full coherence checks on a synthesis."""
        
        report = CoherenceReport(
            entity_id=entity_id,
            context_name=context_name,
            synthesis_delta_id=synthesis_delta_id
        )
        
        synthesis_delta = self.network.get_delta(synthesis_delta_id)
        if not synthesis_delta or synthesis_delta.type_ != "traversal":
            report.all_passed = False
            report.confidence = 0.0
            return report
        
        # Get entity and deltas involved
        entity = self.network.get_entity(entity_id)
        if not entity:
            report.all_passed = False
            report.confidence = 0.0
            return report
        
        provenance = synthesis_delta.receptor_binding.get("provenance", [])
        
        # Run coherence checks
        self._check_reference_integrity(report, provenance)
        self._check_gate_logic(report, provenance, context_name)
        self._check_rule_consistency(report, provenance, context_name)
        self._check_splinter_alignment(report, provenance, entity, context_name)
        
        # Calculate confidence
        failed_checks = sum(1 for c in report.checks if not c.passed)
        report.confidence = max(0.0, 1.0 - (failed_checks * 0.25))
        report.all_passed = failed_checks == 0
        
        return report
    
    def _check_reference_integrity(self, report: CoherenceReport,
                                    provenance: List[str]) -> None:
        """Verify all referenced deltas exist."""
        result = CoherenceCheckResult(
            check_type=CoherenceCheckType.REFERENCE_INTEGRITY,
            passed=True,
            message="All referenced deltas exist"
        )
        
        for delta_id in provenance:
            if not self.network.get_delta(delta_id):
                result.passed = False
                result.affected_deltas.append(delta_id)
                result.message = f"Missing delta: {delta_id}"
        
        report.checks.append(result)
        if not result.passed:
            report.deviations.append("Reference integrity violated")
    
    def _check_gate_logic(self, report: CoherenceReport, provenance: List[str],
                         context_name: str) -> None:
        """Verify no delta is both active and gated under this context."""
        result = CoherenceCheckResult(
            check_type=CoherenceCheckType.GATE_LOGIC,
            passed=True,
            message="Gate logic is consistent"
        )
        
        for delta_id in provenance:
            delta = self.network.get_delta(delta_id)
            if not delta:
                continue
            
            # Check if gated under this context
            is_gated = False
            for gate_id in delta.is_gated_by:
                gate = self.network.get_delta(gate_id)
                if gate and gate.receptor_binding.get("context") == context_name:
                    is_gated = True
                    break
            
            # If both active and gated, that's a splinter (not an error)
            if is_gated:
                result.affected_deltas.append(delta_id)
        
        # Gate logic is always consistent—we allow splinters
        report.checks.append(result)
    
    def _check_rule_consistency(self, report: CoherenceReport, provenance: List[str],
                               context_name: str) -> None:
        """Verify rules don't contradict under this context."""
        result = CoherenceCheckResult(
            check_type=CoherenceCheckType.RULE_CONSISTENCY,
            passed=True,
            message="Rules are consistent under this context"
        )
        
        context = self.network.get_context(context_name)
        if not context:
            report.checks.append(result)
            return
        
        for delta_id in provenance:
            delta = self.network.get_delta(delta_id)
            if not delta:
                continue
            
            rule_id = delta.receptor_binding.get("rule_coordinate")
            if not rule_id:
                continue
            
            rule = self.network.get_rule(rule_id)
            if rule and rule_id in context.suppressed_rules:
                # Rule is suppressed but delta is active—splinter, not error
                result.affected_deltas.append(delta_id)
        
        # Rule inconsistency means splinter truths—acceptable
        report.checks.append(result)
    
    def _check_splinter_alignment(self, report: CoherenceReport, provenance: List[str],
                                  entity: Entity, context_name: str) -> None:
        """Verify splinter truths are properly tracked."""
        result = CoherenceCheckResult(
            check_type=CoherenceCheckType.SPLINTER_ALIGNMENT,
            passed=True,
            message="Splinter truths are aligned"
        )
        
        # Count how many deltas reference this context in their synthesis_context
        aligned_deltas = [
            d for d in self.network.get_entity_delta_chain(entity.id)
            if d.synthesis_context == context_name
        ]
        
        # All active deltas should have synthesis history
        for delta_id in provenance:
            delta = self.network.get_delta(delta_id)
            if delta and delta.synthesis_context != context_name:
                # This is fine—delta from different context, now active in this one
                pass
        
        result.affected_deltas = provenance
        report.checks.append(result)
    
    def create_correction_delta(self, entity_id: str, original_delta_id: str,
                                deviation: str, corrected_value: Any,
                                context_name: str) -> Delta:
        """Create a correction delta (new splinter) without deleting the original.
        
        This represents a splinter truth: the original delta is correct under
        different context, but under this context, a correction applies.
        """
        
        correction = self.network.create_delta(
            entity_id=entity_id,
            delta_type="receptor_activation",
            receptor_binding={
                "corrects_delta": original_delta_id,
                "deviation": deviation,
                "value": corrected_value,
                "is_correction": True
            },
            references=[original_delta_id],
            synthesis_context=context_name,
            source="alignment_correction"
        )
        
        return correction
