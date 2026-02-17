"""
AI Chat Service - Owner Dashboard V2
Uses Claude API to provide intelligent chat about property data.
READ-ONLY: Only analyzes data, no modifications.
"""
import logging
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from app.config import get_settings
from datetime import datetime

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
        funnel_lines += self._format_metric("Sight Unseen (Apps w/o Tour)", funnel.get('sight_unseen'))
        funnel_lines += self._format_metric("Tour-to-App", funnel.get('tour_to_app'))
        funnel_lines += self._format_metric("Lead-to-Tour Rate", funnel.get('lead_to_tour_rate'), "%")
        funnel_lines += self._format_metric("Lead-to-Lease Rate", funnel.get('lead_to_lease_rate'), "%")
        if funnel_lines:
            sections.append(f"LEASING FUNNEL:\n{funnel_lines}")
        
        # Loss-to-Lease
        ltl = property_data.get("loss_to_lease", {})
        if ltl:
            ltl_lines = ""
            if self._has_value(ltl.get('avg_market_rent')):
                ltl_lines += f"- Avg Market Rent: ${ltl.get('avg_market_rent')}\n"
            if self._has_value(ltl.get('avg_actual_rent')):
                ltl_lines += f"- Avg Actual Rent: ${ltl.get('avg_actual_rent')}\n"
            if self._has_value(ltl.get('loss_per_unit')):
                ltl_lines += f"- Loss Per Unit: ${ltl.get('loss_per_unit')}/mo\n"
            if self._has_value(ltl.get('total_monthly_loss')):
                ltl_lines += f"- Total Monthly Loss: ${ltl.get('total_monthly_loss'):,.0f}\n"
            if self._has_value(ltl.get('total_annual_loss')):
                ltl_lines += f"- Total Annual Loss: ${ltl.get('total_annual_loss'):,.0f}\n"
            if ltl_lines:
                sections.append(f"LOSS-TO-LEASE:\n{ltl_lines}")
        
        # Delinquency
        delinq = property_data.get("delinquency", {})
        if delinq:
            del_lines = ""
            del_lines += self._format_metric("Current Resident Delinquency", f"${delinq.get('current_resident_total', 0):,.0f}")
            del_lines += self._format_metric("Former/Collections", f"${delinq.get('former_resident_total', 0):,.0f}")
            del_lines += self._format_metric("Delinquent Units", delinq.get('delinquent_units'))
            del_lines += self._format_metric("Evictions", delinq.get('eviction_count'))
            if del_lines:
                sections.append(f"DELINQUENCY:\n{del_lines}")
        
        # Renewals
        ren = property_data.get("renewals", {})
        if ren:
            ren_lines = ""
            ren_lines += self._format_metric("Renewal Count", ren.get('count_detail', ren.get('count')))
            if self._has_value(ren.get('avg_vs_prior_pct')):
                ren_lines += f"- Avg vs Prior: {ren.get('avg_vs_prior_pct'):+.1f}% (${ren.get('avg_vs_prior', 0):+,.0f}/mo)\n"
            if self._has_value(ren.get('avg_renewal_rent')):
                ren_lines += f"- Avg Renewal Rent: ${ren.get('avg_renewal_rent'):,.0f}\n"
            if ren_lines:
                sections.append(f"RENEWALS:\n{ren_lines}")
        
        # Tradeouts
        to = property_data.get("tradeouts", {})
        if to:
            to_lines = ""
            to_lines += self._format_metric("Trade-out Count", to.get('count'))
            if self._has_value(to.get('avg_pct_change')):
                to_lines += f"- Avg Change: {to.get('avg_pct_change'):+.1f}% (${to.get('avg_dollar_change', 0):+,.0f}/mo)\n"
            if to_lines:
                sections.append(f"TRADE-OUTS (New Leases vs Prior):\n{to_lines}")
        
        # Expirations
        expirations = property_data.get("expirations", [])
        if expirations:
            exp_lines = ""
            for period in expirations[:3]:
                label = period.get("label", "")
                exp_count = period.get("expirations", 0)
                signed = period.get("signed", 0)
                vacating = period.get("vacating", 0)
                exp_lines += f"- {label}: {exp_count} expiring, {signed} renewed, {vacating} vacating\n"
            if exp_lines:
                sections.append(f"LEASE EXPIRATIONS:\n{exp_lines}")
        
        # Reviews
        google = property_data.get("google_reviews", {})
        apt_rev = property_data.get("apartments_reviews", {})
        rev_lines = ""
        if google:
            rev_lines += f"- Google: {google.get('rating', 0):.1f}★ ({google.get('review_count', 0)} reviews, {google.get('response_rate', 0):.0f}% response rate, {google.get('needs_response', 0)} need response)\n"
        if apt_rev:
            rev_lines += f"- Apartments.com: {apt_rev.get('rating', 0):.1f}★ ({apt_rev.get('review_count', 0)} reviews)\n"
        if rev_lines:
            sections.append(f"ONLINE REVIEWS:\n{rev_lines}")
        
        # Move-out reasons
        move_out = property_data.get("move_out_reasons", [])
        if move_out:
            mo_lines = ""
            for r in move_out[:5]:
                mo_lines += f"- {r['category']}: {r['count']} residents\n"
            sections.append(f"TOP MOVE-OUT REASONS:\n{mo_lines}")
        
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

    def _build_portfolio_system_prompt(self, portfolio_data: Dict[str, Any]) -> str:
        """Build system prompt for portfolio-level analysis with asset manager perspective."""
        
        properties = portfolio_data.get("properties", [])
        summary = portfolio_data.get("summary", {})
        
        # Build detailed per-property sections
        property_sections = []
        for prop in properties:
            name = prop.get("name", "Unknown")
            occ = prop.get("occupancy", {})
            pricing = prop.get("pricing", {})
            funnel = prop.get("funnel", {})
            exposure = prop.get("exposure", {})
            delinq = prop.get("delinquency", {})
            renewals = prop.get("renewals", {})
            tradeouts = prop.get("tradeouts", {})
            ltl = prop.get("loss_to_lease", {})
            google = prop.get("google_reviews", {})
            apt_rev = prop.get("apartments_reviews", {})
            expirations = prop.get("expirations", [])
            move_out = prop.get("move_out_reasons", [])
            
            lines = [f"── {name} ──"]
            
            # Occupancy
            units = occ.get("total_units", 0)
            phys_occ = occ.get("physical_occupancy", 0)
            vacant = occ.get("vacant_units", 0)
            aged = occ.get("aged_vacancy_90_plus", 0)
            leased_pct = occ.get("leased_percentage", 0)
            lines.append(f"  Occupancy: {phys_occ:.1f}% physical, {leased_pct:.1f}% leased | {units} units, {vacant} vacant ({aged} aged 90+)")
            
            # Pricing
            in_place = pricing.get("avg_in_place_rent", 0)
            asking = pricing.get("avg_asking_rent", 0)
            growth = pricing.get("rent_growth", 0)
            lines.append(f"  Rent: In-place ${in_place:,.0f}, Asking ${asking:,.0f}, Growth {growth:.1f}%")
            
            # Loss-to-Lease
            if ltl:
                lines.append(f"  Loss-to-Lease: ${ltl.get('loss_per_unit', 0):,.0f}/unit, ${ltl.get('total_monthly_loss', 0):,.0f}/mo (${ltl.get('total_annual_loss', 0):,.0f}/yr)")
            
            # Funnel
            leads = funnel.get("leads", 0)
            tours = funnel.get("tours", 0)
            apps = funnel.get("applications", 0)
            leases = funnel.get("lease_signs", 0)
            l2l_rate = funnel.get("lead_to_lease_rate", 0)
            sight_unseen = funnel.get("sight_unseen", 0)
            tour_to_app = funnel.get("tour_to_app", 0)
            lines.append(f"  Funnel MTD: {leads} leads → {tours} tours → {apps} apps → {leases} leases ({l2l_rate:.1f}% conv)")
            if sight_unseen or tour_to_app:
                lines.append(f"  Funnel Detail: {tour_to_app} tour-to-app, {sight_unseen} applied w/o tour")
            
            # Exposure
            if exposure:
                move_ins = exposure.get("move_ins", 0)
                move_outs = exposure.get("move_outs", 0)
                net = exposure.get("net_absorption", 0)
                notices = exposure.get("notices_30_days", 0)
                lines.append(f"  Movement: {move_ins} move-ins, {move_outs} move-outs, net {net:+d} | {notices} notices (30d)")
            
            # Delinquency
            if delinq:
                curr_del = delinq.get("current_resident_total", 0)
                former_del = delinq.get("former_resident_total", 0)
                del_units = delinq.get("delinquent_units", 0)
                evictions = delinq.get("eviction_count", 0)
                lines.append(f"  Delinquency: ${curr_del:,.0f} current ({del_units} units), ${former_del:,.0f} former/collections, {evictions} evictions")
            
            # Renewals
            if renewals:
                ren_count = renewals.get("count_detail", renewals.get("count", 0))
                avg_vs_prior = renewals.get("avg_vs_prior", 0)
                avg_vs_prior_pct = renewals.get("avg_vs_prior_pct", 0)
                lines.append(f"  Renewals: {ren_count} renewals, avg {avg_vs_prior_pct:+.1f}% vs prior (${avg_vs_prior:+,.0f}/mo)")
            
            # Tradeouts
            if tradeouts:
                to_count = tradeouts.get("count", 0)
                avg_to_change = tradeouts.get("avg_pct_change", 0)
                avg_to_dollar = tradeouts.get("avg_dollar_change", 0)
                lines.append(f"  Trade-outs: {to_count} new leases, avg {avg_to_change:+.1f}% vs prior (${avg_to_dollar:+,.0f}/mo)")
            
            # Expirations
            if expirations:
                exp_lines = []
                for period in expirations[:3]:
                    label = period.get("label", "")
                    exp_count = period.get("expirations", 0)
                    ren_signed = period.get("signed", 0)
                    vacating = period.get("vacating", 0)
                    exp_lines.append(f"{label}: {exp_count} expiring, {ren_signed} renewed, {vacating} vacating")
                if exp_lines:
                    lines.append(f"  Lease Expirations: {' | '.join(exp_lines)}")
            
            # Reviews
            review_parts = []
            if google:
                review_parts.append(f"Google {google.get('rating', 0):.1f}★ ({google.get('review_count', 0)} reviews, {google.get('response_rate', 0):.0f}% response rate, {google.get('needs_response', 0)} need response)")
            if apt_rev:
                review_parts.append(f"Apartments.com {apt_rev.get('rating', 0):.1f}★ ({apt_rev.get('review_count', 0)} reviews)")
            if review_parts:
                lines.append(f"  Reviews: {' | '.join(review_parts)}")
            
            # Move-out reasons
            if move_out:
                reasons = [f"{r['category']} ({r['count']})" for r in move_out[:3]]
                lines.append(f"  Top Move-Out Reasons: {', '.join(reasons)}")
            
            property_sections.append("\n".join(lines))
        
        properties_detail = "\n\n".join(property_sections) if property_sections else "No property data available"
        
        # Calculate portfolio totals
        total_units = summary.get("total_units", 0)
        total_vacant = summary.get("total_vacant", 0)
        avg_occupancy = summary.get("avg_occupancy", 0)
        total_aged = sum(p.get("occupancy", {}).get("aged_vacancy_90_plus", 0) for p in properties)
        total_leads = sum(p.get("funnel", {}).get("leads", 0) for p in properties)
        total_leases = sum(p.get("funnel", {}).get("lease_signs", 0) for p in properties)
        avg_in_place = summary.get("avg_in_place_rent", 0)
        avg_asking = summary.get("avg_asking_rent", 0)
        total_delinquent = sum(p.get("delinquency", {}).get("current_resident_total", 0) for p in properties)
        total_ltl_annual = sum(p.get("loss_to_lease", {}).get("total_annual_loss", 0) for p in properties)
        
        # Identify outliers
        _empty = {"name": "N/A", "occupancy": {}, "funnel": {}}
        best_occ = worst_occ = best_conversion = worst_conversion = _empty
        if properties:
            best_occ = max(properties, key=lambda p: p.get("occupancy", {}).get("physical_occupancy", 0))
            worst_occ = min(properties, key=lambda p: p.get("occupancy", {}).get("physical_occupancy", 100))
            best_conversion = max(properties, key=lambda p: p.get("funnel", {}).get("lead_to_lease_rate", 0))
            worst_conversion = min(properties, key=lambda p: p.get("funnel", {}).get("lead_to_lease_rate", 100))
        
        today = datetime.now().strftime("%B %d, %Y")
        
        return f"""You are an expert Asset Manager and Owner Analyst for a multifamily real estate portfolio. 
You think strategically about NOI optimization, risk mitigation, and portfolio performance.

TODAY'S DATE: {today}

═══════════════════════════════════════════════════════════════════════════════
PORTFOLIO OVERVIEW
═══════════════════════════════════════════════════════════════════════════════

PORTFOLIO TOTALS:
• Total Properties: {len(properties)}
• Total Units: {total_units:,}
• Portfolio Occupancy: {avg_occupancy:.1f}%
• Total Vacant Units: {total_vacant}
• Aged Vacancy (90+ days): {total_aged}
• Avg In-Place Rent: ${avg_in_place:,.0f}
• Avg Asking Rent: ${avg_asking:,.0f}
• Rent Growth Opportunity: {((avg_asking - avg_in_place) / avg_in_place * 100) if avg_in_place > 0 else 0:.1f}%
• Total Leads MTD: {total_leads}
• Total Leases Signed MTD: {total_leases}
• Total Current Delinquency: ${total_delinquent:,.0f}
• Total Annual Loss-to-Lease: ${total_ltl_annual:,.0f}

═══════════════════════════════════════════════════════════════════════════════
PROPERTY-BY-PROPERTY DETAIL
═══════════════════════════════════════════════════════════════════════════════

{properties_detail}

═══════════════════════════════════════════════════════════════════════════════
PERFORMANCE HIGHLIGHTS
═══════════════════════════════════════════════════════════════════════════════
• Highest Occupancy: {best_occ.get("name", "N/A")} ({best_occ.get("occupancy", {}).get("physical_occupancy", 0):.1f}%)
• Lowest Occupancy: {worst_occ.get("name", "N/A")} ({worst_occ.get("occupancy", {}).get("physical_occupancy", 0):.1f}%)
• Best Lead Conversion: {best_conversion.get("name", "N/A")} ({best_conversion.get("funnel", {}).get("lead_to_lease_rate", 0):.1f}%)
• Needs Attention: {worst_conversion.get("name", "N/A")} ({worst_conversion.get("funnel", {}).get("lead_to_lease_rate", 0):.1f}% conversion)

═══════════════════════════════════════════════════════════════════════════════
YOUR ROLE & ANALYSIS FRAMEWORK
═══════════════════════════════════════════════════════════════════════════════

As an Asset Manager, analyze this portfolio through these lenses:

1. **NOI OPTIMIZATION**: Identify rent growth opportunities, loss-to-lease capture, renewal rent pushes
2. **RISK ASSESSMENT**: Flag aged vacancy, delinquency, evictions, low conversion, lease exposure
3. **OPERATIONAL EFFICIENCY**: Compare property performance, identify best practices to replicate
4. **FINANCIAL HEALTH**: Delinquency trends, collections, loss-to-lease, trade-out performance
5. **REPUTATION**: Online review ratings, response rates, review sentiment
6. **RETENTION**: Renewal rates, move-out reasons, lease expiration pipeline

When providing portfolio highlights:
- Lead with the most IMPACTFUL metrics (what affects NOI most)
- Identify OUTLIERS (both positive opportunities and concerns)
- Provide ACTIONABLE recommendations
- Compare properties to identify PATTERNS
- Quantify the FINANCIAL IMPACT when possible

Keep responses strategic and executive-level. Focus on what an owner or asset manager NEEDS to know to make decisions."""

    async def portfolio_chat(
        self,
        message: str,
        portfolio_data: Dict[str, Any],
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Send a message about portfolio-level data and get AI response.
        
        Args:
            message: User's question about the portfolio
            portfolio_data: Aggregated portfolio metrics and per-property data
            history: Previous messages in conversation
        
        Returns:
            AI response string with asset manager perspective
        """
        if not self.client:
            return "Chat is not available. Please configure ANTHROPIC_API_KEY in the backend .env file."
        
        system_prompt = self._build_portfolio_system_prompt(portfolio_data)
        
        # Build messages
        messages = []
        if history:
            for msg in history[-10:]:
                content = msg.get("content", "").strip()
                role = msg.get("role", "user")
                if content and role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
        
        messages.append({"role": "user", "content": message})
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,  # Allow longer responses for portfolio analysis
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Portfolio chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


# Singleton instance
chat_service = ChatService()
