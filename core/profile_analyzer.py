"""
Advanced Profile Analyzer for Jarvis.
Analyzes Linktree and all linked sources to build comprehensive user understanding.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

from core import providers, storage_utils, self_healing

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data" / "user_profile"


class ProfileAnalyzer:
    """Advanced profile analyzer for comprehensive user understanding."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(PROFILE_PATH)
        self.md_storage = storage_utils.get_md_storage(PROFILE_PATH)
        self.healing = self_healing.get_self_healing()
        
        # Platform patterns for identification
        self.platform_patterns = {
            "twitter": ["twitter.com", "x.com"],
            "instagram": ["instagram.com", "ig.com"],
            "linkedin": ["linkedin.com"],
            "facebook": ["facebook.com", "fb.com"],
            "youtube": ["youtube.com", "youtu.be"],
            "tiktok": ["tiktok.com"],
            "github": ["github.com"],
            "website": ["http", "www"],
            "email": ["@", "mail"],
            "phone": ["tel:", "phone", "call"],
            "discord": ["discord.com", "discord.gg"],
            "telegram": ["telegram.org", "t.me"],
            "spotify": ["spotify.com"],
            "apple": ["music.apple.com"],
            "medium": ["medium.com"],
            "substack": ["substack.com"],
            "calendly": ["calendly.com"],
            "linktree": ["linktr.ee", "linktree.com"],
            "tiktok": ["tiktok.com"],
            "pinterest": ["pinterest.com"],
            "reddit": ["reddit.com"],
            "threads": ["threads.net"]
        }
    
    def analyze_linktree(self, linktree_url: str) -> Dict[str, Any]:
        """Analyze Linktree and extract all linked profiles."""
        analysis_session = {
            "linktree_url": linktree_url,
            "start_time": datetime.now().isoformat(),
            "profiles_found": [],
            "companies_found": [],
            "behavior_patterns": {},
            "content_themes": {},
            "detailed_analysis": {},
            "status": "in_progress"
        }
        
        try:
            # Step 1: Extract Linktree content
            linktree_content = self._extract_linktree_content(linktree_url)
            analysis_session["linktree_content"] = linktree_content
            
            # Step 2: Identify all links and platforms
            all_links = self._extract_all_links(linktree_content)
            analysis_session["all_links"] = all_links
            
            # Step 3: Categorize links by platform
            categorized_links = self._categorize_links(all_links)
            analysis_session["categorized_links"] = categorized_links
            
            # Step 4: Deep analysis of each platform
            detailed_profiles = {}
            for platform, links in categorized_links.items():
                if links and platform != "linktree":  # Skip the Linktree itself
                    detailed_profiles[platform] = self._analyze_platform(platform, links)
            
            analysis_session["detailed_analysis"] = detailed_profiles
            analysis_session["profiles_found"] = list(detailed_profiles.keys())
            
            # Step 5: Extract companies and ventures
            companies = self._extract_companies(detailed_profiles)
            analysis_session["companies_found"] = companies
            
            # Step 6: Analyze behavior patterns
            behaviors = self._analyze_behavior_patterns(detailed_profiles)
            analysis_session["behavior_patterns"] = behaviors
            
            # Step 7: Identify content themes
            themes = self._identify_content_themes(detailed_profiles)
            analysis_session["content_themes"] = themes
            
            # Step 8: Generate comprehensive profile
            comprehensive_profile = self._generate_comprehensive_profile(analysis_session)
            analysis_session["comprehensive_profile"] = comprehensive_profile
            
            analysis_session["status"] = "completed"
            
        except Exception as e:
            analysis_session["status"] = "failed"
            analysis_session["error"] = str(e)
        
        analysis_session["end_time"] = datetime.now().isoformat()
        
        # Save analysis
        self.storage.save_txt("linktree_analysis", analysis_session)
        
        return analysis_session
    
    def _extract_linktree_content(self, url: str) -> Dict[str, Any]:
        """Extract content from Linktree using curl."""
        try:
            # Use curl to get the page content
            import subprocess
            
            result = subprocess.run([
                "curl", "-s", "-L", 
                "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                html_content = result.stdout
                
                # Extract key information using regex
                title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
                title = title_match.group(1) if title_match else "Unknown"
                
                # Extract links
                link_matches = re.findall(r'href=[\'"](.*?)[\'"]', html_content)
                links = [link for link in link_matches if link.startswith(('http', 'https', 'mailto:', 'tel:'))]
                
                # Extract description/bio
                desc_match = re.search(r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"](.*?)[\'"]', html_content, re.IGNORECASE)
                description = desc_match.group(1) if desc_match else ""
                
                # Extract profile name from various patterns
                name_patterns = [
                    r'<h1[^>]*>(.*?)</h1>',
                    r'<title>(.*?)\s*\|\s*Linktree</title>',
                    r'"name":\s*"(.*?)"',
                    r'"username":\s*"(.*?)"'
                ]
                
                profile_name = "Unknown"
                for pattern in name_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        profile_name = match.group(1).strip()
                        break
                
                return {
                    "title": title,
                    "profile_name": profile_name,
                    "description": description,
                    "links": links,
                    "html_length": len(html_content),
                    "extraction_method": "curl"
                }
            else:
                return {"error": f"Failed to fetch content: {result.stderr}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_all_links(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and normalize all links from content."""
        links = []
        
        if "links" in content:
            for link in content["links"]:
                if link.startswith(('http', 'https', 'mailto:', 'tel:')):
                    # Normalize URL
                    if link.startswith('http'):
                        parsed = urlparse(link)
                        domain = parsed.netloc.lower()
                        path = parsed.path.lower()
                    else:
                        domain = link.split(':')[0]
                        path = ""
                    
                    links.append({
                        "url": link,
                        "domain": domain,
                        "path": path,
                        "platform": self._identify_platform(domain, path),
                        "type": self._classify_link_type(link)
                    })
        
        return links
    
    def _identify_platform(self, domain: str, path: str) -> str:
        """Identify the platform from domain and path."""
        domain_path = f"{domain} {path}"
        
        for platform, patterns in self.platform_patterns.items():
            for pattern in patterns:
                if pattern in domain_path:
                    return platform
        
        return "unknown"
    
    def _classify_link_type(self, url: str) -> str:
        """Classify the type of link."""
        if url.startswith('mailto:'):
            return "email"
        elif url.startswith('tel:'):
            return "phone"
        elif any(social in url.lower() for social in ['twitter', 'instagram', 'facebook', 'linkedin']):
            return "social_media"
        elif any(business in url.lower() for business in ['linkedin', 'calendly', 'website']):
            return "business"
        elif any(content in url.lower() for content in ['youtube', 'spotify', 'medium', 'substack']):
            return "content"
        else:
            return "other"
    
    def _categorize_links(self, links: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize links by platform."""
        categorized = {}
        
        for link in links:
            platform = link["platform"]
            if platform not in categorized:
                categorized[platform] = []
            categorized[platform].append(link)
        
        return categorized
    
    def _analyze_platform(self, platform: str, links: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Deep analysis of a specific platform."""
        analysis = {
            "platform": platform,
            "links": links,
            "profile_data": {},
            "content_analysis": {},
            "activity_patterns": {},
            "insights": []
        }
        
        try:
            for link in links:
                url = link["url"]
                
                # Extract profile information
                profile_info = self._extract_profile_info(url, platform)
                analysis["profile_data"][url] = profile_info
                
                # Analyze content if accessible
                content_analysis = self._analyze_platform_content(url, platform)
                analysis["content_analysis"][url] = content_analysis
                
                # Small delay to be respectful
                time.sleep(0.5)
            
            # Generate platform-specific insights
            analysis["insights"] = self._generate_platform_insights(platform, analysis)
            
        except Exception as e:
            analysis["error"] = str(e)
        
        return analysis
    
    def _extract_profile_info(self, url: str, platform: str) -> Dict[str, Any]:
        """Extract profile information from a platform URL."""
        profile_info = {
            "url": url,
            "platform": platform,
            "username": self._extract_username(url, platform),
            "profile_type": self._determine_profile_type(url, platform),
            "verification_status": "unknown"
        }
        
        # Platform-specific extraction
        if platform == "twitter":
            profile_info.update(self._extract_twitter_info(url))
        elif platform == "instagram":
            profile_info.update(self._extract_instagram_info(url))
        elif platform == "linkedin":
            profile_info.update(self._extract_linkedin_info(url))
        elif platform == "github":
            profile_info.update(self._extract_github_info(url))
        elif platform == "youtube":
            profile_info.update(self._extract_youtube_info(url))
        
        return profile_info
    
    def _extract_username(self, url: str, platform: str) -> str:
        """Extract username from URL."""
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if platform == "twitter":
                return path_parts[0] if path_parts else ""
            elif platform == "instagram":
                return path_parts[0] if path_parts else ""
            elif platform == "linkedin":
                # LinkedIn URLs are more complex
                if "in/" in url:
                    return url.split("in/")[1].split('/')[0]
                return ""
            elif platform == "github":
                return path_parts[0] if path_parts else ""
            elif platform == "youtube":
                if "/channel/" in url:
                    return url.split("/channel/")[1].split('/')[0]
                elif "/c/" in url:
                    return url.split("/c/")[1].split('/')[0]
                elif "/@" in url:
                    return url.split("/@")[1].split('/')[0]
                return ""
            else:
                return path_parts[0] if path_parts else ""
        except Exception as e:
            return ""
    
    def _determine_profile_type(self, url: str, platform: str) -> str:
        """Determine if it's personal, business, or mixed profile."""
        # Use AI to analyze the URL structure and any accessible content
        try:
            analysis_prompt = f"""Analyze this {platform} URL and determine profile type:
            
URL: {url}

Is this a:
1. Personal profile
2. Business/company profile  
3. Mixed personal/business
4. Unknown

Respond with just the type name."""
            
            response = providers.generate_text(analysis_prompt, max_output_tokens=50)
            return response.strip().lower()
        except Exception as e:
            return "unknown"
    
    def _extract_twitter_info(self, url: str) -> Dict[str, Any]:
        """Extract Twitter-specific information."""
        return {"follower_count": "unknown", "verified": "unknown", "bio": "unknown"}
    
    def _extract_instagram_info(self, url: str) -> Dict[str, Any]:
        """Extract Instagram-specific information."""
        return {"follower_count": "unknown", "verified": "unknown", "bio": "unknown"}
    
    def _extract_linkedin_info(self, url: str) -> Dict[str, Any]:
        """Extract LinkedIn-specific information."""
        return {"profile_type": "unknown", "connections": "unknown", "headline": "unknown"}
    
    def _extract_github_info(self, url: str) -> Dict[str, Any]:
        """Extract GitHub-specific information."""
        return {"repositories": "unknown", "followers": "unknown", "contributions": "unknown"}
    
    def _extract_youtube_info(self, url: str) -> Dict[str, Any]:
        """Extract YouTube-specific information."""
        return {"subscribers": "unknown", "video_count": "unknown", "channel_type": "unknown"}
    
    def _analyze_platform_content(self, url: str, platform: str) -> Dict[str, Any]:
        """Analyze content from a platform (if accessible)."""
        content_analysis = {
            "accessible": False,
            "recent_posts": [],
            "content_themes": [],
            "posting_frequency": "unknown",
            "engagement_patterns": {}
        }
        
        # Note: We'll use AI to analyze public content where possible
        # This is a placeholder for more sophisticated content analysis
        
        return content_analysis
    
    def _generate_platform_insights(self, platform: str, analysis: Dict[str, Any]) -> List[str]:
        """Generate insights about the platform usage."""
        insights = []
        
        try:
            # Use AI to generate insights
            insight_prompt = f"""Generate insights about this {platform} presence:

Platform: {platform}
Number of profiles: {len(analysis['links'])}
Profile data: {json.dumps(analysis['profile_data'], indent=2)}

Provide 3-5 key insights about:
1. Professional vs personal focus
2. Content strategy
3. Engagement approach
4. Brand consistency
5. Unique characteristics

Format as a JSON array of strings."""
            
            response = providers.generate_text(insight_prompt, max_output_tokens=300)
            
            # Try to parse as JSON array
            try:
                insights = json.loads(response)
                if isinstance(insights, list):
                    return insights
            except Exception as e:
                pass
            
            # Fallback: split by newlines
            insights = [line.strip() for line in response.split('\n') if line.strip()]
            
        except Exception as e:
            insights = [f"Unable to generate detailed insights for {platform}"]
        
        return insights[:5]  # Limit to 5 insights
    
    def _extract_companies(self, detailed_profiles: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract company information from profiles."""
        companies = []
        
        # Look for company mentions in LinkedIn, websites, and bios
        for platform, data in detailed_profiles.items():
            for url, profile_data in data.get("profile_data", {}).items():
                # Use AI to extract company information
                try:
                    extraction_prompt = f"""Extract company information from this profile:

Platform: {platform}
URL: {url}
Data: {json.dumps(profile_data, indent=2)}

Look for:
1. Company names mentioned
2. Job titles/positions
3. Business ventures
4. Startup involvement

Return as JSON array with company_name, role, and confidence (0-1)."""
                    
                    response = providers.generate_text(extraction_prompt, max_output_tokens=200)
                    
                    try:
                        extracted = json.loads(response)
                        if isinstance(extracted, list):
                            for item in extracted:
                                if isinstance(item, dict) and item.get("company_name"):
                                    companies.append({
                                        "company_name": item["company_name"],
                                        "role": item.get("role", "unknown"),
                                        "platform": platform,
                                        "source_url": url,
                                        "confidence": item.get("confidence", 0.5)
                                    })
                    except Exception as e:
                        pass
                        
                except Exception as e:
                    continue
        
        # Remove duplicates and sort by confidence
        unique_companies = []
        seen = set()
        
        for company in sorted(companies, key=lambda x: x.get("confidence", 0), reverse=True):
            key = f"{company['company_name'].lower()}_{company['platform']}"
            if key not in seen:
                unique_companies.append(company)
                seen.add(key)
        
        return unique_companies
    
    def _analyze_behavior_patterns(self, detailed_profiles: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze behavior patterns across platforms."""
        patterns = {
            "posting_consistency": "unknown",
            "content_types": [],
            "engagement_style": "unknown",
            "professional_vs_personal": "unknown",
            "brand_voice": "unknown",
            "platform_preferences": {}
        }
        
        try:
            # Use AI to analyze patterns
            pattern_prompt = f"""Analyze behavior patterns from these social media profiles:

{json.dumps(detailed_profiles, indent=2)}

Analyze and provide insights on:
1. Posting consistency and frequency
2. Types of content shared
3. Engagement style (active/passive, formal/casual)
4. Professional vs personal balance
5. Brand voice and communication style
6. Platform preferences and strategy

Return as JSON object with these keys."""
            
            response = providers.generate_text(pattern_prompt, max_output_tokens=400)
            
            try:
                patterns.update(json.loads(response))
            except Exception as e:
                pass
                
        except Exception as e:
            pass
        
        return patterns
    
    def _identify_content_themes(self, detailed_profiles: Dict[str, Any]) -> List[str]:
        """Identify recurring content themes."""
        themes = []
        
        try:
            # Use AI to identify themes
            theme_prompt = f"""Identify content themes from these profiles:

{json.dumps(detailed_profiles, indent=2)}

What are the main topics, interests, and themes discussed across these platforms?
List 5-10 key themes as a JSON array of strings."""
            
            response = providers.generate_text(theme_prompt, max_output_tokens=200)
            
            try:
                themes = json.loads(response)
                if isinstance(themes, list):
                    return themes
            except Exception as e:
                pass
            
            # Fallback: extract themes manually
            themes = [line.strip() for line in response.split('\n') if line.strip()]
            
        except Exception as e:
            pass
        
        return themes[:10]  # Limit to 10 themes
    
    def _generate_comprehensive_profile(self, analysis_session: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive user profile."""
        profile = {
            "profile_name": analysis_session.get("linktree_content", {}).get("profile_name", "Unknown"),
            "bio": analysis_session.get("linktree_content", {}).get("description", ""),
            "total_platforms": len(analysis_session.get("profiles_found", [])),
            "platforms": analysis_session.get("profiles_found", []),
            "companies": analysis_session.get("companies_found", []),
            "behavior_patterns": analysis_session.get("behavior_patterns", {}),
            "content_themes": analysis_session.get("content_themes", []),
            "professional_summary": "",
            "personal_summary": "",
            "recommendations": [],
            "analysis_date": datetime.now().isoformat()
        }
        
        try:
            # Generate comprehensive summaries using AI
            summary_prompt = f"""Generate a comprehensive profile summary based on this analysis:

Name: {profile['profile_name']}
Bio: {profile['bio']}
Platforms: {', '.join(profile['platforms'])}
Companies: {json.dumps(profile['companies'], indent=2)}
Behaviors: {json.dumps(profile['behavior_patterns'], indent=2)}
Themes: {', '.join(profile['content_themes'])}

Provide:
1. professional_summary: Professional identity and focus
2. personal_summary: Personal interests and values
3. recommendations: 3-5 recommendations for online presence optimization

Return as JSON object with these keys."""
            
            response = providers.generate_text(summary_prompt, max_output_tokens=600)
            
            try:
                summaries = json.loads(response)
                profile.update(summaries)
            except Exception as e:
                pass
                
        except Exception as e:
            pass
        
        return profile
    
    def commit_to_memory(self, profile_data: Dict[str, Any]) -> bool:
        """Commit the comprehensive profile to memory."""
        try:
            # Save to multiple memory systems
            timestamp = datetime.now().isoformat()
            
            # 1. Save comprehensive profile
            self.storage.save_txt("user_comprehensive_profile", profile_data)
            
            # 2. Save individual components
            self.storage.save_txt("user_platforms", profile_data.get("platforms", []))
            self.storage.save_txt("user_companies", profile_data.get("companies", []))
            self.storage.save_txt("user_behaviors", profile_data.get("behavior_patterns", {}))
            self.storage.save_txt("user_themes", profile_data.get("content_themes", []))
            
            # 3. Create markdown documentation
            markdown_content = f"""# User Profile Analysis

## Basic Information
- **Name**: {profile_data.get('profile_name', 'Unknown')}
- **Bio**: {profile_data.get('bio', '')}
- **Analysis Date**: {profile_data.get('analysis_date', '')}

## Online Presence
- **Total Platforms**: {profile_data.get('total_platforms', 0)}
- **Platforms**: {', '.join(profile_data.get('platforms', []))}

## Companies & Ventures
{self._format_companies(profile_data.get('companies', []))}

## Behavior Patterns
{self._format_behaviors(profile_data.get('behavior_patterns', {}))}

## Content Themes
{self._format_themes(profile_data.get('content_themes', []))}

## Professional Summary
{profile_data.get('professional_summary', '')}

## Personal Summary
{profile_data.get('personal_summary', '')}

## Recommendations
{self._format_recommendations(profile_data.get('recommendations', []))}
"""
            
            self.md_storage.save_md("user_profile", markdown_content)
            
            # 4. Log to system memory
            self.storage.log_event("profile_memory", "committed_to_memory", {
                "profile_name": profile_data.get('profile_name'),
                "platforms_count": profile_data.get('total_platforms', 0),
                "companies_count": len(profile_data.get('companies', [])),
                "timestamp": timestamp
            })
            
            return True
            
        except Exception as e:
            print(f"Failed to commit to memory: {e}")
            return False
    
    def _format_companies(self, companies: List[Dict[str, Any]]) -> str:
        """Format companies for markdown."""
        if not companies:
            return "No companies identified."
        
        formatted = []
        for company in companies:
            formatted.append(f"- **{company['company_name']}** ({company.get('role', 'Unknown')}) - {company['platform']}")
        
        return "\n".join(formatted)
    
    def _format_behaviors(self, behaviors: Dict[str, Any]) -> str:
        """Format behaviors for markdown."""
        if not behaviors:
            return "No behavior patterns identified."
        
        formatted = []
        for key, value in behaviors.items():
            formatted.append(f"- **{key.replace('_', ' ').title()}**: {value}")
        
        return "\n".join(formatted)
    
    def _format_themes(self, themes: List[str]) -> str:
        """Format themes for markdown."""
        if not themes:
            return "No content themes identified."
        
        return "\n".join([f"- {theme}" for theme in themes])
    
    def _format_recommendations(self, recommendations: List[str]) -> str:
        """Format recommendations for markdown."""
        if not recommendations:
            return "No recommendations available."
        
        return "\n".join([f"1. {rec}" for rec in recommendations])
    
    def get_stored_profile(self) -> Optional[Dict[str, Any]]:
        """Retrieve the stored comprehensive profile."""
        return self.storage.load_txt("user_comprehensive_profile")
    
    def update_profile_notes(self, new_notes: str) -> bool:
        """Add new notes to the profile."""
        try:
            current_notes = self.storage.load_txt("profile_notes", "list") or []
            current_notes.append({
                "note": new_notes,
                "timestamp": datetime.now().isoformat()
            })
            self.storage.save_txt("profile_notes", current_notes)
            return True
        except Exception as e:
            return False


# Global analyzer instance
_analyzer: Optional[ProfileAnalyzer] = None


def get_profile_analyzer() -> ProfileAnalyzer:
    """Get the global profile analyzer instance."""
    global _analyzer
    if not _analyzer:
        _analyzer = ProfileAnalyzer()
    return _analyzer
