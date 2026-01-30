"""
AI Chat Service - Owner Dashboard V2
Uses Claude API to provide intelligent chat about property data.
READ-ONLY: Only analyzes data, no modifications.
"""
import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from app.config import get_settings

logger = logging.getLogger(__name__)


class ChatService:
    """
    AI Chat service that knows about property data and can answer questions.
    """
    
    def __init__(self):
        self.client = None
        self.model = "claude-sonnet-4-20250514"
        settings = get_settings()
        if settings.anthropic_api_key:
            self.client = Anthropic(api_key=settings.anthropic_api_key)
        else:
            logger.warning("ANTHROPIC_API_KEY not set - chat will be disabled")
    
    def is_available(self) -> bool:
        """Check if chat service is available."""
        return self.client is not None
    
    def _has_value(self, val: Any) -> bool:
        """Check if a value is meaningful (not None, 0, empty, or 'N/A')."""
        if val is None:
            return False
        if isinstance(val, (int, float)) and val == 0:
            return False
        if isinstance(val, str) and (not val.strip() or val == 'N/A'):
            return False
        if isinstance(val, list) and len(val) == 0:
            return False
        return True
    
    def _format_metric(self, label: str, value: Any, suffix: str = "") -> str:
        """Format a metric line only if value exists."""
        if not self._has_value(value):
            return ""
        return f"- {label}: {value}{suffix}\n"
    
    def _build_system_prompt(self, property_data: Dict[str, Any]) -> str:
        """Build system prompt with property context. Only includes existing data."""
        
        # Extract key metrics for context
        occupancy = property_data.get("occupancy", {})
        pricing = property_data.get("pricing", {})
        exposure = property_data.get("exposure", {})
        funnel = property_data.get("funnel", {})
        units = property_data.get("units", [])
        residents = property_data.get("residents", [])
        
        # Build property summary
        property_name = property_data.get("property_name", "Unknown Property")
        property_id = property_data.get("property_id", "")
        
        # Build sections dynamically - only include data that exists
        sections = []
        
        # Property context
        occ_lines = ""
        occ_lines += self._format_metric("Total Units", occupancy.get('total_units'))
        occ_lines += self._format_metric("Physical Occupancy", occupancy.get('physical_occupancy'), "%")
        occ_lines += self._format_metric("Leased Percentage", occupancy.get('leased_percentage'), "%")
        occ_lines += self._format_metric("Vacant Units", occupancy.get('vacant_units'))
        occ_lines += self._format_metric("Aged Vacancy (90+ days)", occupancy.get('aged_vacancy_90_plus'))
        if occ_lines:
            sections.append(f"OCCUPANCY:\n{occ_lines}")
        
        # Exposure
        exp_lines = ""
        exp_lines += self._format_metric("30-Day Exposure", exposure.get('exposure_30_days'), " units")
        exp_lines += self._format_metric("60-Day Exposure", exposure.get('exposure_60_days'), " units")
        exp_lines += self._format_metric("Notices (30 days)", exposure.get('notices_30_days'))
        exp_lines += self._format_metric("Move-ins", exposure.get('move_ins'))
        exp_lines += self._format_metric("Move-outs", exposure.get('move_outs'))
        exp_lines += self._format_metric("Net Absorption", exposure.get('net_absorption'))
        if exp_lines:
            sections.append(f"EXPOSURE & MOVEMENT:\n{exp_lines}")
        
        # Pricing
        price_lines = ""
        if self._has_value(pricing.get('avg_in_place_rent')):
            price_lines += f"- Avg In-Place Rent: ${pricing.get('avg_in_place_rent')}\n"
        if self._has_value(pricing.get('avg_asking_rent')):
            price_lines += f"- Avg Asking Rent: ${pricing.get('avg_asking_rent')}\n"
        price_lines += self._format_metric("Rent Growth", pricing.get('avg_rent_growth'), "%")
        if price_lines:
            sections.append(f"PRICING:\n{price_lines}")
        
        # Funnel
        funnel_lines = ""
        funnel_lines += self._format_metric("Leads", funnel.get('leads'))
        funnel_lines += self._format_metric("Tours", funnel.get('tours'))
        funnel_lines += self._format_metric("Applications", funnel.get('applications'))
        funnel_lines += self._format_metric("Lease Signs", funnel.get('lease_signs'))
        funnel_lines += self._format_metric("Lead-to-Tour Rate", funnel.get('lead_to_tour_rate'), "%")
        funnel_lines += self._format_metric("Lead-to-Lease Rate", funnel.get('lead_to_lease_rate'), "%")
        if funnel_lines:
            sections.append(f"LEASING FUNNEL:\n{funnel_lines}")
        
        # Units and residents
        if len(units) > 0:
            sections.append(f"UNITS DATA:\n{len(units)} units loaded with details including floorplan, bedrooms, bathrooms, square feet, market rent, status, and days vacant.")
        if len(residents) > 0:
            sections.append(f"RESIDENTS DATA:\n{len(residents)} resident records loaded with move-in/move-out dates, rent amounts, and lease information.")
        
        data_context = "\n\n".join(sections) if sections else "Limited data available for this property."
        
        return f"""You are an AI assistant for the Owner Dashboard, helping property owners and managers understand their property data.

PROPERTY: {property_name} ({property_id})

{data_context}

GUIDELINES:
1. Only analyze the data provided above - do not mention missing data.
2. Provide actionable insights based on what IS available.
3. Use specific numbers from the data when answering.
4. Highlight concerns (e.g., high vacancy, low conversion rates) proactively.
5. Keep responses focused and concise.
6. For complex analysis, break down your reasoning.

You can help with occupancy analysis, pricing insights, leasing funnel efficiency, identifying risks and opportunities, and suggesting improvements based on the available data."""

    async def chat(
        self,
        message: str,
        property_data: Dict[str, Any],
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Send a message and get AI response with property context.
        
        Args:
            message: User's question
            property_data: Current property metrics and data
            history: Previous messages in conversation
        
        Returns:
            AI response string
        """
        if not self.client:
            return "Chat is not available. Please configure ANTHROPIC_API_KEY in the backend .env file."
        
        system_prompt = self._build_system_prompt(property_data)
        
        # Build messages
        messages = []
        if history:
            for msg in history[-10:]:  # Last 10 messages for context
                content = msg.get("content", "").strip()
                role = msg.get("role", "user")
                if content and role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


# Singleton instance
chat_service = ChatService()
