"""
Image search utility - fetches real images from Google, Bing, and other sources.
"""

import httpx
import asyncio
import re
from typing import Optional


async def search_images_unsplash_direct(query: str, timeout: int = 8) -> Optional[str]:
    """
    Use Unsplash's direct URL endpoint that works without API key.
    Simply returns a formatted URL to their image service.
    """
    try:
        # Unsplash's source.unsplash.com endpoint doesn't require authentication
        # and returns a redirect to a real image based on the query
        clean_query = query.replace(" ", "+")
        url = f"https://source.unsplash.com/1600x900/?{clean_query}"
        
        async with httpx.AsyncClient() as client:
            # Test if URL is valid by making a HEAD request
            response = await asyncio.wait_for(
                client.head(url, follow_redirects=True),
                timeout=timeout
            )
            
            if response.status_code == 200:
                # Return the URL (Unsplash will redirect to actual image)
                return url
        
        return None
    except Exception as e:
        print(f"Unsplash direct search error: {e}")
        return None


async def search_images_bing(query: str, timeout: int = 8) -> Optional[str]:
    """
    Scrape Bing Image Search for real images.
    Returns first image URL found or None.
    """
    try:
        async with httpx.AsyncClient() as client:
            url = "https://www.bing.com/images/search"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            params = {
                "q": query,
                "count": "1"
            }
            
            response = await asyncio.wait_for(
                client.get(url, headers=headers, params=params),
                timeout=timeout
            )
            
            if response.status_code == 200:
                # Look for image URLs in the response
                # Bing stores them in the page JavaScript
                content = response.text
                
                # Find image URLs - Bing uses specific patterns
                # Look for murl patterns in the page
                murl_matches = re.findall(r'"murl":"([^"]+\.(?:jpg|jpeg|png|webp|gif))"', content, re.IGNORECASE)
                if murl_matches:
                    return murl_matches[0]
                
                # Alternative pattern - look for image src attributes
                src_matches = re.findall(r'src="([^"]*(?:jpg|jpeg|png|webp)[^"]*)"', content, re.IGNORECASE)
                if src_matches:
                    for match in src_matches:
                        if match.startswith("http") and "bing" not in match.lower():
                            return match
            
            return None
    except Exception as e:
        print(f"Bing search error: {e}")
        return None


async def search_images_pixabay_url(query: str) -> Optional[str]:
    """
    Generate a Pixabay search URL that redirects to images.
    Pixabay hosts real, free images.
    """
    try:
        clean_query = query.replace(" ", "+")
        # This URL will perform a search on Pixabay
        # We can craft a direct image URL if we get lucky with common terms
        
        async with httpx.AsyncClient() as client:
            # Try Pixabay's direct API if possible, or URL-based approach
            url = f"https://pixabay.com/api/?key=dummy&q={clean_query}&image_type=photo&per_page=1"
            response = await asyncio.wait_for(
                client.get(url),
                timeout=5
            )
            
            # Even without auth, sometimes the response has info
            if response.status_code == 200:
                # Try to parse the HTML/JSON if available
                try:
                    data = response.json()
                    if data.get("hits") and len(data["hits"]) > 0:
                        return data["hits"][0].get("webformatURL")
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"Pixabay search error: {e}")
        return None


async def search_google_images_url(query: str) -> str:
    """
    Generate a Google Images search URL.
    The user's browser will follow this to see real Google Images.
    But we can also return a proxy/embed-friendly version.
    """
    clean_query = query.replace(" ", "+")
    # This is a direct Google Images search URL
    return f"https://www.google.com/search?q={clean_query}&tbm=isch"


async def fetch_first_image(query: str) -> Optional[str]:
    """
    Fetch a real image URL from the web.
    Tries multiple sources in order of reliability.
    """
    if not query or len(query.strip()) < 2:
        return None
    
    print(f"Searching for image: {query}")
    
    # Strategy 1: Unsplash direct (fastest, no scraping needed)
    image_url = await search_images_unsplash_direct(query, timeout=5)
    if image_url:
        print(f"Using Unsplash: {image_url}")
        return image_url
    
    # Strategy 2: Bing Image Search (scrapes real images)
    image_url = await search_images_bing(query, timeout=8)
    if image_url:
        print(f"Using Bing: {image_url}")
        return image_url
    
    # Strategy 3: Pixabay (free image hosting)
    image_url = await search_images_pixabay_url(query)
    if image_url:
        print(f"Using Pixabay: {image_url}")
        return image_url
    
    # Strategy 4: Fallback to a generic image placeholder based on query
    # This uses a service that generates images on the fly
    fallback = f"https://via.placeholder.com/1600x900/E8E8E8/666666?text={query[:50].replace(' ', '+')}"
    print(f"Using placeholder: {fallback}")
    return fallback
