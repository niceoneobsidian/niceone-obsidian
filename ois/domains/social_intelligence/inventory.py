# Canonical 394-entry Social Intelligence Fabric inventory is defined here.
# The implementation uses existing OIS registries/contracts; this module is a
# specification manifest, not proof that every entry is implemented.

from __future__ import annotations

REGISTRY_MAP = {
    "social_intelligence": ("capability_registry", "CapabilityContract", "P0"),
    "entity": ("capability_registry", "CapabilityContract", "P0"),
    "audience": ("capability_registry", "CapabilityContract", "P0"),
    "competitor": ("capability_registry", "CapabilityContract", "P0"),
    "creative": ("capability_registry", "CapabilityContract", "P0"),
    "viral": ("memory", "MemorySchema + CapabilityContract", "P0"),
    "agents": ("agent_registry", "AgentContract", "P0"),
    "capabilities": ("capability_registry", "CapabilityContract", "P0"),
    "platform": ("tool_registry", "ToolContract", "P0"),
    "platform_connectors": ("tool_registry", "ToolContract", "P0"),
    "content": ("capability_registry", "CapabilityContract", "P1"),
    "quality": ("validation", "Validator + CapabilityContract", "P0"),
    "campaign": ("workflow_registry", "WorkflowDefinition + CapabilityContract", "P1"),
    "workflow": ("workflow_registry", "WorkflowDefinition", "P0"),
    "scheduling": ("workflow_registry", "WorkflowDefinition + ToolContract", "P1"),
    "approval": ("policy", "Policy/ApprovalContract", "P0"),
    "inbox": ("capability_registry", "CapabilityContract + ToolContract", "P1"),
    "analytics": ("measurement", "MeasurementContract", "P1"),
    "prediction": ("measurement", "PredictionContract + CapabilityContract", "P1"),
    "attribution": ("measurement", "AttributionContract", "P1"),
    "experiments": ("learning", "ExperimentContract", "P1"),
    "learning": ("learning", "LearningContract", "P1"),
    "memory": ("memory", "MemorySchema", "P0"),
    "artifacts": ("validation", "ArtifactSchema", "P0"),
    "models": ("model_registry", "ModelProviderContract", "P1"),
    "seo": ("capability_registry", "CapabilityContract", "P2"),
    "integration": ("tool_registry", "ToolContract", "P1"),
    "governance": ("policy", "PolicyContract", "P0"),
    "recovery": ("recovery", "RecoveryContract", "P0"),
    "observability": ("observability", "TelemetryContract", "P1"),
}

# The complete names are stored in grouped tuples to keep the manifest
# reviewable. Each group is mapped through REGISTRY_MAP above.
STRUCTURES = {
  "social_intelligence": ["Social Intelligence Fabric","Social Source Registry","Social Signal Schema","Social Research Tools","Multi-source Intelligence Collector","Source Reliability/Quality Scoring","Cross-source Signal Correlation","Cross-source Clustering","Signal Deduplication","Signal Normalization","Signal Relevance Scoring","Signal Velocity Analysis","Trend Detection","Trend Ranking","Trend Lifecycle","Trend Breakout Detection","Trend Forecasting","Watchlists","Research Brief Generation","Social Intelligence Scoring"],
  "entity": ["Entity Resolution","Entity Registry","Person Intelligence","Company Intelligence","Brand Intelligence","Product Intelligence","Topic Intelligence","Technology Intelligence","Community Intelligence","Entity Profiles","Entity Activity","Entity Sentiment","Entity Relationships","Entity Influence","Entity Content History","Entity Recent Events","Entity Watchlists"],
  "audience": ["Audience Intelligence Engine","Audience Segmentation","Audience Profiles","Audience Interests","Audience Pain Points","Audience Desires","Audience Objections","Audience Behavioral Patterns","Audience Language/Terminology","Audience Engagement Patterns","Audience Sentiment","Audience Intent","Audience Opportunity Detection","Audience → Content Matching"],
  "competitor": ["Competitor Registry","Competitor Discovery","Competitor Monitoring","Competitor Content Collection","Competitor Strategy Analysis","Competitor Posting Analysis","Competitor Engagement Analysis","Competitor Trend Analysis","Competitor Creative Analysis","Competitor Content Comparison","Competitor Opportunity Detection","Competitor Change Detection"],
  "creative": ["Creative Intelligence Engine","Creative Discovery","Creative Qualification","Creative Ranking","Winning Creative Detection","Creative Pattern Extraction","Multimodal Creative Analysis","Video Analysis","Audio Analysis","Transcript Analysis","Scene Analysis","Visual Pattern Analysis","Hook Analysis","Narrative Analysis","Emotion Analysis","Pacing Analysis","CTA Analysis","Offer Analysis","Editing Pattern Analysis","Audience Trigger Analysis","Brand Adaptation","Creative Strategy Generation"],
  "viral": ["Viral Pattern Memory","Hook Memory","Opening Pattern Memory","Narrative Pattern Memory","Emotional Pattern Memory","Identity Trigger Memory","Pacing Pattern Memory","Visual Pattern Memory","CTA Pattern Memory","Offer Pattern Memory","Format Pattern Memory","Platform Pattern Memory","Audience Pattern Memory","Performance Pattern Memory","Pattern Confidence","Pattern Evidence","Pattern Versioning","Pattern Lifecycle"],
  "agents": ["Social Agent Registry","Social Research Agent","Audience Intelligence Agent","Competitor Intelligence Agent","Creative Intelligence Agent","Content Strategy Agent","Content Generation Agent","Content Adaptation Agent","Campaign Agent","Scheduling Agent","Publishing Agent","Analytics Agent","Attribution Agent","Learning Agent","Social Supervisor"],
  "capabilities": ["Social Capability Registry"],
  "platform": ["Platform Connector Registry"],
  "platform_connectors": ["X","Instagram","Facebook","TikTok","YouTube","LinkedIn","Threads","Pinterest","Reddit","Discord","Google Business","Bluesky","Hacker News","GitHub","Web/News sources"],
  "content": ["Content Intelligence Engine","Content Idea Generation","Content Brief","Content Drafting","Content Variation","Hook Generation","Caption Generation","Script Generation","CTA Generation","Hashtag Generation","Keyword Generation","Thread Generation","UGC Script Generation","Platform-native Generation","Platform Adaptation","Content Repurposing","Content History","Generation Parameters","Content Versioning","Publishing Intent"],
  "quality": ["Content Quality Engine","Content Score","Brand Voice Validation","Brand Consistency","Factuality Validation","Platform Compliance","Safety Validation","SEO Evaluation","Readability Evaluation","Audience-Fit Evaluation","Creative-Fit Evaluation","CTA Evaluation","Hook Evaluation","Evidence/Grounding Evaluation"],
  "campaign": ["Campaign Registry","Campaign Model","Campaign Objective","Campaign Audience","Campaign Strategy","Campaign Content","Campaign Channels","Campaign Schedule","Campaign Experiments","Campaign Metrics","Campaign Attribution","Campaign Learning"],
  "workflow": ["Social Workflow Registry","Workflow Definition","Workflow Trigger","Workflow Condition","Workflow Action","Workflow Branch","Workflow Approval","Workflow Retry","Workflow Timeout","Workflow Recovery","Workflow Completion","Workflow Failure","Conditional Publishing","Automated Follow-up","Automated Content Pipeline"],
  "scheduling": ["Content Calendar","Smart Scheduler","Posting Plans","Publishing Queue","Best-Time Detection","Recurring Scheduling","Bulk Scheduling","Cross-Posting","Platform Adaptation Before Publishing","Content Recycling","Recycle Candidate Detection","Freshness Validation","Automated Rescheduling","Publishing Conditions"],
  "approval": ["Human-in-the-Loop Gate","Approval Queue","Agent Inbox","Content Approval","Campaign Approval","Publishing Approval","Tool Authorization","Escalation","Human Edit","Reject","Approve","Request Revision"],
  "inbox": ["Social Inbox","Comment Collection","Mention Collection","Message Collection","Comment Classification","Sentiment Detection","Intent Detection","Saved Replies","Response Suggestions","Comment Triggers","Escalation Rules","Engagement Workflow"],
  "analytics": ["Social Analytics Engine","Performance Measurement","Reach Measurement","Impression Measurement","View Measurement","Watch-Time Measurement","Retention Measurement","Engagement Measurement","Share Measurement","Save Measurement","Follower Growth","Click Measurement","Conversion Measurement","Revenue Measurement","Content Performance","Platform Performance","Campaign Performance","Audience Performance","Creative Performance"],
  "prediction": ["Performance Prediction","Content Score Prediction","Engagement Prediction","Best-Time Prediction","Trend Forecasting","Content Opportunity Prediction","Conversion Probability","Creative Performance Prediction"],
  "attribution": ["Content Attribution","Campaign Attribution","Platform Attribution","Audience Attribution","Creative Attribution","Conversion Attribution","Revenue Attribution","Touchpoint History","Attribution Records"],
  "experiments": ["Experiment Registry","Experiment Definition","Experiment Objective","Experiment Hypothesis","Experiment Arms","Content Variants","Audience Variants","Platform Variants","Timing Variants","Creative Variants","Control Groups","Experiment Metrics","Experiment Evaluation","Experiment Winner","Experiment Evidence"],
  "learning": ["Social Learning Loop","Performance → Reward","Pattern Extraction","Strategy Learning","Audience Learning","Creative Learning","Platform Learning","Timing Learning","Campaign Learning","Experiment Learning","Reward Attribution","Strategy Optimization","Policy/Strategy Candidate Generation"],
  "memory": ["Audience Memory","Competitor Memory","Trend Memory","Topic Memory","Entity Memory","Creative Memory","Viral Pattern Memory","Content Performance Memory","Platform Behavior Memory","Campaign Memory","Experiment Memory","Strategy Memory","Evidence Memory","Decision Memory"],
  "artifacts": ["Social Signal Artifact","Trend Artifact","Entity Profile Artifact","Audience Intelligence Brief","Competitor Intelligence Brief","Creative Intelligence Brief","Research Brief","Content Strategy Artifact","Campaign Strategy Artifact","Creative Pattern Artifact","Experiment Report","Performance Report","Attribution Report","Learning Report"],
  "models": ["Provider Abstraction","Model Registry Integration","Model Capability Discovery","Model Selection","Structured Output Contract","Generation Configuration","Cost Accounting","Token/Usage Tracking","Model Evaluation","Model Fallback","Model Routing"],
  "seo": ["SEO Intelligence","Keyword Intelligence","SEO Metadata","SEO Content Evaluation","SEO Quality Score","Search Intent","SEO Content Structure","SEO Export Contract"],
  "integration": ["Webhook Trigger","HTTP Trigger","External Workflow Trigger","API Adapter","MCP Tool Adapter","CLI Adapter","Zapier-style Integration Boundary","Make-style Integration Boundary","External Event Ingestion"],
  "governance": ["Social Policy","Publishing Policy","Platform Policy","Content Safety Policy","Brand Policy","Approval Policy","Tool Permission Policy","Rate-Limit Policy","Tenant Isolation","RBAC","Audit Trail","Execution Authorization","Least Privilege"],
  "recovery": ["Bounded Retry","Backoff","Checkpoint","Resume","Fallback Tool","Fallback Model","Workflow Recovery","Publishing Recovery","Connector Failure Handling","Rate-Limit Recovery","Partial Execution Recovery","Escalation","Circuit Breaker"],
  "observability": ["Social Execution Telemetry","Agent Telemetry","Tool Telemetry","Workflow Telemetry","Publishing Telemetry","Model Usage","Token/Cost Metrics","Latency","Error Rates","Approval Rates","Content Quality Scores","Prediction Accuracy","Attribution Quality","Learning Performance"],
}

CATEGORY_ORDER = tuple(STRUCTURES)


def iter_inventory():
    for category in CATEGORY_ORDER:
        registry, contract, priority = REGISTRY_MAP[category]
        for name in STRUCTURES[category]:
            slug = name.lower().replace(" ", ".").replace("/", ".").replace("→", "to").replace("-", ".")
            yield {"id": slug, "name": name, "category": category, "target_registry": registry, "target_contract": contract, "priority": priority, "integration_mode": "extend_existing_contract", "implementation_status": "specified_not_implemented_by_this_inventory"}


INVENTORY = tuple(iter_inventory())

if len(INVENTORY) != 394:
    raise RuntimeError(f"Expected 394 structures, got {len(INVENTORY)}")
