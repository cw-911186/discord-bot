import discord
from discord.ext import commands, tasks
import requests
import asyncio
import os
from datetime import datetime, time
import json
from collections import deque

class RateLimiter:
    def __init__(self, max_requests=20, time_window=1):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
    
    async def wait_if_needed(self):
        """필요시 대기하여 Rate Limit 준수"""
        now = asyncio.get_event_loop().time()
        
        # 시간 창 밖의 요청들 제거
        while self.requests and self.requests[0] <= now - self.time_window:
            self.requests.popleft()
        
        # 요청 한도에 도달했으면 대기
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.time_window - now + 0.1
            if sleep_time > 0:
                print(f"Rate limit 대기: {sleep_time:.1f}초")
                await asyncio.sleep(sleep_time)
                return await self.wait_if_needed()  # 재귀적으로 다시 확인
        
        # 현재 요청 시간 기록
        self.requests.append(now)

class LOLRanking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.riot_api_key = os.getenv('RIOT_API_KEY')
        self.base_url = "https://kr.api.riotgames.com"
        
        # Rate Limiter 설정 (보수적으로)
        self.rate_limiter = RateLimiter(max_requests=18, time_window=1)  # 20보다 작게
        
        # 채널 ID 설정
        self.solo_rank_channel_id = int(os.getenv('SOLO_RANK_CHANNEL_ID', '0'))
        self.flex_rank_channel_id = int(os.getenv('FLEX_RANK_CHANNEL_ID', '0'))
        
        # 티어 순위 매핑
        self.tier_priority = {
            'CHALLENGER': 9, 'GRANDMASTER': 8, 'MASTER': 7,
            'DIAMOND': 6, 'EMERALD': 5, 'PLATINUM': 4,
            'GOLD': 3, 'SILVER': 2, 'BRONZE': 1, 'IRON': 0
        }
        
        # 캐시된 랭킹 데이터 저장
        self.cached_ranking_data = []
        
        # 최대 처리 인원 제한 (30분 동안 처리 가능한 안전한 수)
        self.max_users_per_update = 100
        
        # 일일 업데이트 스케줄러 시작 (태스크 정의 후에 시작)
        # 태스크는 클래스 정의 완료 후 자동으로 시작됨

    def cog_unload(self):
        self.data_collection.cancel()
        self.ranking_update.cancel()

    @staticmethod
    def extract_lol_nickname(display_name: str) -> tuple:
        """닉네임에서 롤 닉네임과 태그 추출: '별명/출생년도/롤닉네임#태그' -> ('롤닉네임', '태그')"""
        try:
            parts = display_name.split('/')
            if len(parts) >= 3:
                lol_full = parts[2].strip()
                
                # '#' 태그가 있는 경우만 처리
                if '#' in lol_full:
                    name_parts = lol_full.split('#')
                    if len(name_parts) == 2:
                        lol_name = name_parts[0].strip()
                        tag = name_parts[1].strip().upper()  # 태그는 대문자로 통일
                        
                        # 빈 문자열 체크
                        if lol_name and tag:
                            return (lol_name, tag)
                
            return (None, None)
        except:
            return (None, None)

    async def make_api_request(self, url: str, headers: dict) -> dict:
        """Rate Limit을 준수하는 API 요청"""
        await self.rate_limiter.wait_if_needed()
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 429:  # Rate Limited
                retry_after = int(response.headers.get('Retry-After', 1))
                print(f"Rate limit 도달, {retry_after}초 대기")
                await asyncio.sleep(retry_after)
                return await self.make_api_request(url, headers)  # 재시도
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API 오류: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"요청 오류: {e}")
            return None

    async def get_riot_puuid(self, game_name: str, tag_line: str) -> str:
        """Rate Limited PUUID 조회"""
        if not self.riot_api_key:
            return None
            
        url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        headers = {"X-Riot-Token": self.riot_api_key}
        
        result = await self.make_api_request(url, headers)
        return result.get('puuid') if result else None

    async def get_summoner_by_puuid(self, puuid: str) -> dict:
        """Rate Limited 소환사 정보 조회"""
        if not puuid:
            return None
            
        url = f"{self.base_url}/lol/summoner/v4/summoners/by-puuid/{puuid}"
        headers = {"X-Riot-Token": self.riot_api_key}
        
        return await self.make_api_request(url, headers)

    async def get_rank_info(self, summoner_id: str) -> dict:
        """Rate Limited 랭크 정보 조회"""
        if not summoner_id:
            return {}
            
        url = f"{self.base_url}/lol/league/v4/entries/by-summoner/{summoner_id}"
        headers = {"X-Riot-Token": self.riot_api_key}
        
        result = await self.make_api_request(url, headers)
        if not result:
            return {}
            
        ranks = {}
        for entry in result:
            queue_type = entry.get('queueType')
            if queue_type == 'RANKED_SOLO_5x5':
                ranks['solo'] = {
                    'tier': entry.get('tier', 'UNRANKED'),
                    'rank': entry.get('rank', ''),
                    'lp': entry.get('leaguePoints', 0),
                    'wins': entry.get('wins', 0),
                    'losses': entry.get('losses', 0)
                }
            elif queue_type == 'RANKED_FLEX_SR':
                ranks['flex'] = {
                    'tier': entry.get('tier', 'UNRANKED'),
                    'rank': entry.get('rank', ''),
                    'lp': entry.get('leaguePoints', 0),
                    'wins': entry.get('wins', 0),
                    'losses': entry.get('losses', 0)
                }
        return ranks

    async def get_user_rank_data(self, member: discord.Member) -> dict:
        """멤버의 랭크 데이터 가져오기 (Rate Limited)"""
        lol_name, tag = self.extract_lol_nickname(member.display_name)
        if not lol_name or not tag:
            return None
            
        print(f"처리 중: {member.display_name} ({lol_name}#{tag})")
        
        # 1단계: PUUID 가져오기
        puuid = await self.get_riot_puuid(lol_name, tag)
        if not puuid:
            print(f"  PUUID 조회 실패: {lol_name}#{tag}")
            return None
            
        # 2단계: 소환사 정보 가져오기
        summoner = await self.get_summoner_by_puuid(puuid)
        if not summoner:
            print(f"  소환사 정보 조회 실패: {lol_name}#{tag}")
            return None
            
        # 3단계: 랭크 정보 가져오기
        ranks = await self.get_rank_info(summoner['id'])
        
        print(f"  완료: {lol_name}#{tag}")
        return {
            'discord_name': member.display_name,
            'lol_name': lol_name,
            'tag': tag,
            'summoner_name': summoner.get('name', lol_name),
            'level': summoner.get('summonerLevel', 0),
            'ranks': ranks
        }

    def calculate_rank_score(self, rank_data: dict) -> int:
        """랭크 점수 계산"""
        if not rank_data:
            return 0
            
        tier = rank_data.get('tier', 'UNRANKED')
        rank = rank_data.get('rank', '')
        lp = rank_data.get('lp', 0)
        
        if tier == 'UNRANKED':
            return 0
            
        tier_score = self.tier_priority.get(tier, 0) * 1000
        rank_values = {'I': 4, 'II': 3, 'III': 2, 'IV': 1}
        rank_score = rank_values.get(rank, 0) * 100
        
        return tier_score + rank_score + lp

    def create_ranking_embed(self, ranking_data: list, queue_type: str) -> discord.Embed:
        """순위표 임베드 생성"""
        title = f"🏆 리그오브레전드 {'솔로랭크' if queue_type == 'solo' else '자유랭크'} 순위"
        embed = discord.Embed(title=title, color=discord.Color.gold())
        
        if not ranking_data:
            embed.description = "랭크 데이터가 없습니다."
            return embed
            
        top_players = ranking_data[:20]
        ranking_text = ""
        
        for i, player in enumerate(top_players, 1):
            rank_info = player['ranks'].get(queue_type, {})
            
            if rank_info.get('tier') == 'UNRANKED':
                tier_text = "언랭크"
            else:
                tier = rank_info.get('tier', 'UNRANKED')
                rank = rank_info.get('rank', '')
                lp = rank_info.get('lp', 0)
                tier_text = f"{tier} {rank} {lp}LP"
                
            wins = rank_info.get('wins', 0)
            losses = rank_info.get('losses', 0)
            total_games = wins + losses
            winrate = round((wins / total_games * 100), 1) if total_games > 0 else 0
            
            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            ranking_text += f"{rank_emoji} **{player['summoner_name']}**\n"
            ranking_text += f"    {tier_text} | {wins}승 {losses}패 ({winrate}%)\n\n"
        
        embed.description = ranking_text
        embed.set_footer(text=f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return embed

    async def update_rankings(self):
        """개선된 랭킹 업데이트"""
        guild = self.bot.get_guild(ALLOWED_GUILDS[0])
        if not guild:
            return
            
        print(f"랭킹 업데이트 시작... (최대 {self.max_users_per_update}명)")
        
        # 롤 닉네임이 있는 멤버만 필터링
        eligible_members = []
        for member in guild.members:
            if member.bot:
                continue
            if self.extract_lol_nickname(member.display_name):
                eligible_members.append(member)
        
        # 제한된 수만 처리
        members_to_process = eligible_members[:self.max_users_per_update]
        print(f"처리 대상: {len(members_to_process)}명 (전체 {len(eligible_members)}명 중)")
        
        all_data = []
        
        # 순차적으로 처리 (Rate Limit 준수)
        for i, member in enumerate(members_to_process, 1):
            try:
                print(f"[{i}/{len(members_to_process)}] {member.display_name}")
                rank_data = await self.get_user_rank_data(member)
                if rank_data:
                    all_data.append(rank_data)
                    
            except Exception as e:
                print(f"오류 발생 ({member.display_name}): {e}")
                continue
        
        # 솔로랭크 순위
        solo_ranking = sorted([p for p in all_data if 'solo' in p['ranks']], 
                            key=lambda x: self.calculate_rank_score(x['ranks']['solo']), 
                            reverse=True)
        
        # 자유랭크 순위
        flex_ranking = sorted([p for p in all_data if 'flex' in p['ranks']], 
                            key=lambda x: self.calculate_rank_score(x['ranks']['flex']), 
                            reverse=True)
        
        # 채널 업데이트
        await self.update_ranking_channel(self.solo_rank_channel_id, solo_ranking, 'solo')
        await self.update_ranking_channel(self.flex_rank_channel_id, flex_ranking, 'flex')
        
        print(f"업데이트 완료: 솔로 {len(solo_ranking)}명, 자유 {len(flex_ranking)}명")

    async def update_ranking_channel(self, channel_id: int, ranking_data: list, queue_type: str):
        """순위표 채널 업데이트"""
        if not channel_id:
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        # 기존 메시지 삭제
        async for message in channel.history(limit=100):
            if message.author == self.bot.user:
                await message.delete()
                
        # 새 순위표 전송
        embed = self.create_ranking_embed(ranking_data, queue_type)
        await channel.send(embed=embed)

    @tasks.loop(time=time(hour=0, minute=0))
    async def daily_update(self):
        """일일 자동 업데이트"""
        await self.update_rankings()

    @daily_update.before_loop
    async def before_daily_update(self):
        await self.bot.wait_until_ready()

    @commands.command(name="랭킹수집")
    @commands.has_permissions(administrator=True)
    async def manual_collect(self, ctx):
        """수동으로 랭킹 데이터 수집"""
        await ctx.send("🔄 랭킹 데이터 수집을 시작합니다... (최대 30분 소요)")
        await self.collect_ranking_data()
        await ctx.send("✅ 랭킹 데이터 수집이 완료되었습니다!")

    @commands.command(name="랭킹발행")
    @commands.has_permissions(administrator=True)
    async def manual_publish(self, ctx):
        """수동으로 순위표 발행"""
        await ctx.send("📊 순위표를 발행합니다...")
        await self.publish_rankings()
        await ctx.send("✅ 순위표 발행이 완료되었습니다!")
        
    @commands.command(name="랭킹업데이트")
    @commands.has_permissions(administrator=True)
    async def manual_full_update(self, ctx):
        """수동으로 전체 랭킹 업데이트 (수집 + 발행)"""
        await ctx.send("🔄 전체 랭킹 업데이트를 시작합니다...")
        await self.collect_ranking_data()
        await self.publish_rankings()
        await ctx.send("✅ 전체 랭킹 업데이트가 완료되었습니다!")

async def setup(bot):
    cog = LOLRanking(bot)
    await bot.add_cog(cog)
    # Cog 로드 완료 후 태스크 시작
    cog.data_collection.start()
    cog.ranking_update.start()