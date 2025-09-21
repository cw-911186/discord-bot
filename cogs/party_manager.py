import discord
from discord.ext import commands
from discord import ui, app_commands
import asyncio

# --- 파티 카드 View (참가/관전 버튼) ---
class PartyCardView(ui.View):
    def __init__(self, bot, party_vc_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.party_vc_id = party_vc_id

    async def update_embed(self, interaction: discord.Interaction):
        """파티 카드 임베드를 최신 정보로 업데이트하는 함수"""
        cog = self.bot.get_cog('PartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info:
            await interaction.message.delete()
            self.stop()
            return

        # 참가자/관전자 목록을 짧은 이름으로 변환
        guild = interaction.guild
        participants_names = []
        for uid in party_info['participants']:
            member = guild.get_member(uid)
            participants_names.append(cog.get_short_name(member.display_name) if member else f"나간 유저({uid})")

        spectators_names = []
        for uid in party_info['spectators']:
            member = guild.get_member(uid)
            spectators_names.append(cog.get_short_name(member.display_name) if member else f"나간 유저({uid})")

        embed = interaction.message.embeds[0]
        embed.set_field_at(2, name="👥 참가자 목록", value='\n'.join(participants_names) if participants_names else "없음", inline=True)
        embed.set_field_at(3, name="👀 관전자 목록", value='\n'.join(spectators_names) if spectators_names else "없음", inline=True)
        embed.set_field_at(1, name="📊 현재 인원", value=f"{len(party_info['participants'])} / {party_info['max_size']}", inline=False)
        
        await interaction.message.edit(embed=embed)

    async def handle_join(self, interaction: discord.Interaction, join_type: str):
        user = interaction.user
        if not user.voice or user.voice.channel.id != self.party_vc_id:
            await interaction.response.send_message("❗ 먼저 파티 음성 채널에 참여해야 합니다.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        cog = self.bot.get_cog('PartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info: return

        # 다른 목록에 있으면 제거
        if join_type == 'participant' and user.id in party_info['spectators']:
            party_info['spectators'].remove(user.id)
        elif join_type == 'spectator' and user.id in party_info['participants']:
            party_info['participants'].remove(user.id)

        # 인원 수 체크 (참가자만)
        if join_type == 'participant' and user.id not in party_info['participants'] and len(party_info['participants']) >= party_info['max_size']:
             await interaction.followup.send("❗ 파티 인원이 가득 찼습니다.", ephemeral=True)
             return
        
        # 목록에 추가 또는 제거 (토글 방식)
        target_set = party_info['participants'] if join_type == 'participant' else party_info['spectators']
        if user.id in target_set:
            target_set.remove(user.id) # 이미 있으면 제거
        else:
            target_set.add(user.id) # 없으면 추가
        
        await self.update_embed(interaction)

    @ui.button(label="참가/취소", style=discord.ButtonStyle.success, custom_id="party_join_participant_toggle")
    async def join_participant(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'participant')

    @ui.button(label="관전/취소", style=discord.ButtonStyle.secondary, custom_id="party_join_spectator_toggle")
    async def join_spectator(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'spectator')


# --- 파티 설정 View (드롭다운, 생성 버튼) ---
class PartySetupView(ui.View):
    def __init__(self, bot, author, thread):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.thread = thread
        self.selected_mode = None
        self.selected_size = None

    @ui.select(
        placeholder="게임 모드를 선택하세요...",
        options=[
            discord.SelectOption(label="일반", value="일반"),
            discord.SelectOption(label="듀오랭크", value="듀오랭크"),
            discord.SelectOption(label="자유랭크", value="자유랭크"),
            discord.SelectOption(label="칼바람 나락", value="칼바람 나락"),
            discord.SelectOption(label="아레나", value="아레나"),
        ]
    )
    async def mode_select(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_mode = select.values[0]
        await interaction.response.send_message(f"🎮 게임 모드: **{self.selected_mode}** 선택됨", ephemeral=True)

    @ui.select(
        placeholder="파티 인원 수를 선택하세요...",
        options=[
            discord.SelectOption(label="2인", value="2"), 
            discord.SelectOption(label="3인", value="3"),
            discord.SelectOption(label="4인", value="4"), 
            discord.SelectOption(label="5인", value="5"),
            discord.SelectOption(label="16인", value="16"),
        ]
    )
    async def size_select(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_size = int(select.values[0])
        await interaction.response.send_message(f"👥 파티 인원: **{self.selected_size}명** 선택됨", ephemeral=True)

    @ui.button(label="🎉 파티 생성", style=discord.ButtonStyle.primary)
    async def create_party_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❗ 파티 생성자만 버튼을 누를 수 있습니다.", ephemeral=True)
        
        if not self.selected_mode or not self.selected_size:
            return await interaction.response.send_message("❗ 게임 모드와 인원 수를 모두 선택해야 합니다.", ephemeral=True)

        await interaction.response.defer()

        cog = self.bot.get_cog('PartyManager')
        if not cog or not self.author.voice: 
            return
        
        party_vc = self.author.voice.channel
        
        party_info = cog.active_parties.get(party_vc.id)
        if not party_info: 
            return
            
        party_info.update({
            "game_mode": self.selected_mode,
            "max_size": self.selected_size,
        })
        party_info["participants"].add(self.author.id)

        # 짧은 이름 추출
        short_name = cog.get_short_name(self.author.display_name)

        # 채널 이름 변경 및 잠금 해제
        await party_vc.edit(
            name=f"{short_name}님의 파티",
            user_limit=None  # 인원 제한 해제
        )

        # 파티 카드 생성 (메인 채널에)
        main_channel = self.bot.get_channel(self.bot.party_text_channel_id)
        embed = discord.Embed(title=f"🎉 {short_name}님의 파티가 열렸습니다!", color=discord.Color.blue())
        embed.add_field(name="🕹️ 게임 모드", value=self.selected_mode, inline=False)
        embed.add_field(name="📊 현재 인원", value=f"1 / {self.selected_size}", inline=False)
        embed.add_field(name="👥 참가자 목록", value=short_name, inline=True)
        embed.add_field(name="👀 관전자 목록", value="없음", inline=True)
        embed.set_footer(text=f"음성 채널: {short_name}님의 파티")

        party_card_view = PartyCardView(self.bot, party_vc.id)
        party_card_msg = await main_channel.send(embed=embed, view=party_card_view)
        party_info["party_card_message_id"] = party_card_msg.id
        
        # 성공 메시지를 스레드에 보냄
        await interaction.followup.send("✅ 파티가 성공적으로 생성되었습니다! 메인 채널에서 파티 카드를 확인하세요.")
        
        # 스레드 자동 삭제 (5초 후)
        await asyncio.sleep(5)
        try:
            await self.thread.delete()
        except:
            pass
        
        self.stop()

    async def on_timeout(self):
        # 타임아웃 시 음성 채널 삭제 및 스레드 정리
        if self.author.voice and "도우미" in self.author.voice.channel.name:
            await self.author.voice.channel.delete(reason="파티 생성 시간 초과")
        
        try:
            await self.thread.delete()
        except:
            pass


# --- Cog 클래스 ---
class PartyManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_parties = {}
        self.setup_threads = {}  # 진행 중인 설정 스레드 추적
        bot.add_view(PartyCardView(bot, 0))

    @staticmethod
    def get_short_name(display_name: str) -> str:
        """'별명/출생년도/롤닉네임' 형식에서 '별명'만 추출합니다."""
        try:
            return display_name.split('/')[0].strip()
        except:
            return display_name # 형식에 맞지 않으면 전체 이름 반환

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        trigger_channel_id = self.bot.party_trigger_channel_id
        
        # 파티 생성 채널에 입장한 경우
        if after.channel and after.channel.id == trigger_channel_id:
            # 이미 설정 중인 스레드가 있다면 무시
            if member.id in self.setup_threads:
                await member.move_to(before.channel)  # 원래 채널로 되돌림
                return
                
            category = after.channel.category
            
            # 짧은 이름 추출
            short_name = self.get_short_name(member.display_name)
            
            # 임시 음성 채널 생성 (1명 제한으로 잠금)
            temp_vc = await category.create_voice_channel(
                name=f"{short_name}님의 파티설정 도우미",
                user_limit=1  # 파티 생성자만 입장 가능
            )
            await member.move_to(temp_vc)

            # 메인 텍스트 채널에서 비공개 스레드 생성
            main_channel = self.bot.get_channel(self.bot.party_text_channel_id)
            if main_channel:
                try:
                    # 비공개 스레드 생성
                    thread = await main_channel.create_thread(
                        name=f"{short_name}님의 파티-생성-도우미",
                        type=discord.ChannelType.private_thread,
                        auto_archive_duration=60  # 1시간 후 자동 아카이브
                    )
                    
                    # 파티 생성자를 스레드에 추가
                    await thread.add_user(member)
                    
                    # 설정 메시지 생성
                    embed = discord.Embed(
                        title="🎈 파티 생성 도우미", 
                        description=f"{member.mention}님, 파티 정보를 설정해주세요.\n\n"
                                   f"⚠️ 이 스레드는 당신만 볼 수 있는 비공개 공간입니다.",
                        color=discord.Color.gold()
                    )
                    setup_view = PartySetupView(self.bot, member, thread)
                    setup_msg = await thread.send(embed=embed, view=setup_view)

                    # 추적 정보 저장
                    self.setup_threads[member.id] = thread.id
                    self.active_parties[temp_vc.id] = {
                        "leader_id": member.id,
                        "setup_message_id": setup_msg.id,
                        "thread_id": thread.id,
                        "party_card_message_id": None,
                        "game_mode": None, 
                        "max_size": 0,
                        "participants": set(), 
                        "spectators": set()
                    }

                except Exception as e:
                    # 스레드 생성 실패 시 대체 방안
                    await temp_vc.delete()
                    if member.voice:
                        await member.move_to(before.channel)

        # 파티 채널에서 나간 경우
        if before.channel and before.channel.id in self.active_parties:
            # 채널 업데이트 0.5초 대기
            await asyncio.sleep(0.5)
            # 채널 객체를 다시 가져와 정확한 멤버 수를 확인
            channel = self.bot.get_channel(before.channel.id)
            if channel and not channel.members:
                party_info = self.active_parties.pop(before.channel.id)
                
                # 설정 스레드 정리
                if party_info["leader_id"] in self.setup_threads:
                    del self.setup_threads[party_info["leader_id"]]
                
                # 파티 카드 삭제
                if party_info.get("party_card_message_id"):
                    main_channel = self.bot.get_channel(self.bot.party_text_channel_id)
                    try:
                        msg = await main_channel.fetch_message(party_info["party_card_message_id"])
                        await msg.delete()
                    except discord.NotFound:
                        pass
                
                # 설정 스레드 삭제
                if party_info.get("thread_id"):
                    try:
                        thread = self.bot.get_channel(party_info["thread_id"])
                        if thread:
                            await thread.delete()
                    except:
                        pass
                
                await before.channel.delete(reason="파티 채널에 사용자가 없음")

async def setup(bot: commands.Bot):
    await bot.add_cog(PartyManager(bot))