import discord
from discord.ext import commands
from discord import ui
import asyncio

# --- 자유 파티 카드 View ---
class FreePartyCardView(ui.View):
    def __init__(self, bot, party_vc_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.party_vc_id = party_vc_id

    def has_verified_role(self, member: discord.Member) -> bool:
        """멤버가 인증완료 역할을 가지고 있는지 확인"""
        VERIFIED_ROLE_NAME = "인증완료"
        return any(role.name == VERIFIED_ROLE_NAME for role in member.roles)

    async def update_embed(self, interaction: discord.Interaction):
        """파티 카드 임베드를 최신 정보로 업데이트"""
        cog = self.bot.get_cog('FreePartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info:
            await interaction.message.delete()
            self.stop()
            return

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
        
        # 인증완료 역할 확인
        if not self.has_verified_role(user):
            await interaction.response.send_message(
                "❌ **파티 참여 권한이 없습니다.**\n\n"
                "파티에 참여하려면 먼저 온보딩 과정을 완료해야 합니다.\n"
                "📍 #입장-온보딩 채널에서 닉네임 설정과 역할 선택을 완료해주세요.", 
                ephemeral=True
            )
            return
        
        if not user.voice or user.voice.channel.id != self.party_vc_id:
            await interaction.response.send_message("❗ 먼저 파티 음성 채널에 참여해야 합니다.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        cog = self.bot.get_cog('FreePartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info: return

        if join_type == 'participant':
            if user.id in party_info['participants']:
                await interaction.followup.send("이미 참가자로 등록되어 있습니다.", ephemeral=True)
                return
            
            if user.id in party_info['spectators']:
                party_info['spectators'].remove(user.id)
            
            if len(party_info['participants']) >= party_info['max_size']:
                party_info['spectators'].add(user.id)
                await interaction.followup.send("파티 인원이 가득 차서 관전자로 배정되었습니다.", ephemeral=True)
            else:
                party_info['participants'].add(user.id)
                await interaction.followup.send("참가자로 배정되었습니다.", ephemeral=True)
        
        elif join_type == 'spectator':
            if user.id in party_info['spectators']:
                await interaction.followup.send("이미 관전자로 등록되어 있습니다.", ephemeral=True)
                return
            
            if user.id in party_info['participants']:
                party_info['participants'].remove(user.id)
            
            party_info['spectators'].add(user.id)
            await interaction.followup.send("관전자로 배정되었습니다.", ephemeral=True)
        
        await self.update_embed(interaction)

    @ui.button(label="참가자", style=discord.ButtonStyle.success, custom_id="free_party_join_participant")
    async def join_participant(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'participant')

    @ui.button(label="관전자", style=discord.ButtonStyle.secondary, custom_id="free_party_join_spectator")
    async def join_spectator(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'spectator')


# --- 게임 이름 입력 모달 ---
class FreePartyGameModal(ui.Modal, title="게임 이름 입력"):
    game_name = ui.TextInput(
        label="플레이할 게임 이름을 입력하세요",
        placeholder="예: 발로란트, 오버워치2, 피파24, 마인크래프트, 스팀게임 등...",
        required=True,
        max_length=50
    )

    def __init__(self, bot, author, thread, selected_size):
        super().__init__()
        self.bot = bot
        self.author = author
        self.thread = thread
        self.selected_size = selected_size

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cog = self.bot.get_cog('FreePartyManager')
        if not cog or not self.author.voice: 
            return
        
        party_vc = self.author.voice.channel
        party_info = cog.active_parties.get(party_vc.id)
        if not party_info: 
            return
            
        party_info.update({
            "game_mode": self.game_name.value,
            "max_size": self.selected_size,
        })
        party_info["participants"].add(self.author.id)

        short_name = cog.get_short_name(self.author.display_name)

        # 채널 이름 변경 및 잠금 해제
        await party_vc.edit(
            name=f"{short_name}님의 파티",
            user_limit=None
        )

        # 자유 파티 카드 생성
        main_channel = self.bot.get_channel(self.bot.free_party_text_channel_id)
        embed = discord.Embed(title=f"🎉 {short_name}님의 파티가 열렸습니다!", color=discord.Color.purple())
        embed.add_field(name="🎮 게임", value=self.game_name.value, inline=False)
        embed.add_field(name="📊 현재 인원", value=f"1 / {self.selected_size}", inline=False)
        embed.add_field(name="👥 참가자 목록", value=short_name, inline=True)
        embed.add_field(name="👀 관전자 목록", value="없음", inline=True)
        embed.set_footer(text=f"음성 채널: {short_name}님의 파티")

        party_card_view = FreePartyCardView(self.bot, party_vc.id)
        party_card_msg = await main_channel.send(embed=embed, view=party_card_view)
        party_info["party_card_message_id"] = party_card_msg.id
        
        await interaction.followup.send("✅ 자유 파티가 성공적으로 생성되었습니다! 메인 채널에서 파티 카드를 확인하세요.")
        
        # 스레드 자동 삭제
        await asyncio.sleep(5)
        try:
            await self.thread.delete()
        except:
            pass


# --- 자유 파티 설정 View ---
class FreePartySetupView(ui.View):
    def __init__(self, bot, author, thread):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.thread = thread
        self.selected_size = None

    @ui.select(
        placeholder="파티 인원 수를 선택하세요...",
        options=[
            discord.SelectOption(label="2인", value="2"), 
            discord.SelectOption(label="3인", value="3"),
            discord.SelectOption(label="4인", value="4"), 
            discord.SelectOption(label="5인", value="5"),
            discord.SelectOption(label="6인", value="6"),
            discord.SelectOption(label="8인", value="8"),
            discord.SelectOption(label="10인", value="10"),
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
        
        if not self.selected_size:
            return await interaction.response.send_message("❗ 인원 수를 먼저 선택해야 합니다.", ephemeral=True)

        # 게임 입력 모달 표시
        await interaction.response.send_modal(FreePartyGameModal(self.bot, self.author, self.thread, self.selected_size))

    async def on_timeout(self):
        if self.author.voice and "도우미" in self.author.voice.channel.name:
            await self.author.voice.channel.delete(reason="자유 파티 생성 시간 초과")
        
        try:
            await self.thread.delete()
        except:
            pass


# --- 자유 파티 관리 Cog ---
class FreePartyManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_parties = {}
        self.setup_threads = {}
        bot.add_view(FreePartyCardView(bot, 0))

    @staticmethod
    def get_short_name(display_name: str) -> str:
        """별명만 추출"""
        try:
            return display_name.split('/')[0].strip()
        except:
            return display_name

    def has_verified_role(self, member: discord.Member) -> bool:
        """멤버가 인증완료 역할을 가지고 있는지 확인"""
        VERIFIED_ROLE_NAME = "인증완료"
        return any(role.name == VERIFIED_ROLE_NAME for role in member.roles)

    async def update_party_card(self, party_info):
        """파티 카드 업데이트"""
        if not party_info.get("party_card_message_id"):
            return
            
        main_channel = self.bot.get_channel(self.bot.free_party_text_channel_id)
        try:
            msg = await main_channel.fetch_message(party_info["party_card_message_id"])
            embed = msg.embeds[0]
            
            guild = main_channel.guild
            participants_names = []
            for uid in party_info['participants']:
                user = guild.get_member(uid)
                participants_names.append(self.get_short_name(user.display_name) if user else f"나간 유저({uid})")

            spectators_names = []
            for uid in party_info['spectators']:
                user = guild.get_member(uid)
                spectators_names.append(self.get_short_name(user.display_name) if user else f"나간 유저({uid})")

            embed.set_field_at(2, name="👥 참가자 목록", value='\n'.join(participants_names) if participants_names else "없음", inline=True)
            embed.set_field_at(3, name="👀 관전자 목록", value='\n'.join(spectators_names) if spectators_names else "없음", inline=True)
            embed.set_field_at(1, name="📊 현재 인원", value=f"{len(party_info['participants'])} / {party_info['max_size']}", inline=False)
            
            await msg.edit(embed=embed)
        except:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 자유 파티 생성 채널에 입장한 경우
        if after.channel and after.channel.id == self.bot.free_party_trigger_channel_id:
            # 인증완료 역할 확인
            if not self.has_verified_role(member):
                try:
                    dm_embed = discord.Embed(
                        title="❌ 자유 파티 생성 권한 없음",
                        description="자유 파티를 생성하려면 먼저 **온보딩 과정**을 완료해야 합니다.\n\n"
                                   "🔹 #입장-온보딩 채널에서 닉네임 설정과 역할 선택을 완료해주세요.\n"
                                   "🔹 온보딩 완료 후 '인증완료' 역할을 받으면 파티 생성이 가능합니다.",
                        color=discord.Color.red()
                    )
                    await member.send(embed=dm_embed)
                except:
                    welcome_channel = self.bot.get_channel(self.bot.welcome_channel_id)
                    if welcome_channel:
                        temp_msg = await welcome_channel.send(
                            f"❌ {member.mention}님, 자유 파티 생성을 위해서는 온보딩 과정을 먼저 완료해주세요!"
                        )
                        await asyncio.sleep(5)
                        try:
                            await temp_msg.delete()
                        except:
                            pass
                
                if before.channel:
                    await member.move_to(before.channel)
                else:
                    await member.move_to(None)
                return
            
            # 이미 설정 중인 스레드가 있다면 무시
            if member.id in self.setup_threads:
                await member.move_to(before.channel)
                return
                
            category = after.channel.category
            short_name = self.get_short_name(member.display_name)
            
            # 임시 음성 채널 생성
            temp_vc = await category.create_voice_channel(
                name=f"{short_name}님의 자유파티설정 도우미",
                user_limit=1
            )
            await member.move_to(temp_vc)

            # 자유 파티 메인 채널에서 비공개 스레드 생성
            main_channel = self.bot.get_channel(self.bot.free_party_text_channel_id)
            if main_channel:
                try:
                    thread = await main_channel.create_thread(
                        name=f"{short_name}님의 자유파티-생성-도우미",
                        type=discord.ChannelType.private_thread,
                        auto_archive_duration=60
                    )
                    
                    await thread.add_user(member)
                    
                    embed = discord.Embed(
                        title="🎈 자유 파티 생성 도우미", 
                        description=f"{member.mention}님, 자유 파티 정보를 설정해주세요.\n\n"
                                   f"🎮 **자유 파티**는 롤 외의 다양한 게임을 즐길 수 있는 파티입니다.\n"
                                   f⚠️ 이 스레드는 당신만 볼 수 있는 비공개 공간입니다.",
                        color=discord.Color.purple()
                    )
                    setup_view = FreePartySetupView(self.bot, member, thread)
                    setup_msg = await thread.send(embed=embed, view=setup_view)

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
                    await temp_vc.delete()
                    if member.voice:
                        await member.move_to(before.channel)

        # 자유 파티 채널에 입장한 경우
        if after.channel and after.channel.id in self.active_parties:
            party_info = self.active_parties[after.channel.id]
            
            # 인증완료 역할 확인 (파티장 제외)
            if member.id != party_info['leader_id'] and not self.has_verified_role(member):
                try:
                    dm_embed = discord.Embed(
                        title="❌ 자유 파티 참여 권한 없음",
                        description="자유 파티에 참여하려면 먼저 **온보딩 과정**을 완료해야 합니다.\n\n"
                                   "🔹 #입장-온보딩 채널에서 닉네임 설정과 역할 선택을 완료해주세요.\n"
                                   "🔹 온보딩 완료 후 '인증완료' 역할을 받으면 파티 참여가 가능합니다.",
                        color=discord.Color.red()
                    )
                    await member.send(embed=dm_embed)
                except:
                    welcome_channel = self.bot.get_channel(self.bot.welcome_channel_id)
                    if welcome_channel:
                        temp_msg = await welcome_channel.send(
                            f"❌ {member.mention}님, 자유 파티 참여를 위해서는 온보딩 과정을 먼저 완료해주세요!"
                        )
                        await asyncio.sleep(5)
                        try:
                            await temp_msg.delete()
                        except:
                            pass
                
                if before.channel:
                    await member.move_to(before.channel)
                else:
                    await member.move_to(None)
                return
            
            # 파티장이 재입장한 경우 무조건 참가자로 등록
            if member.id == party_info['leader_id']:
                if member.id not in party_info['participants']:
                    party_info['spectators'].discard(member.id)
                    party_info['participants'].add(member.id)
                    await self.update_party_card(party_info)
                return
            
            # 새로 입장한 멤버만 자동 할당
            if (member.id not in party_info['participants'] and 
                member.id not in party_info['spectators']):
                
                if len(party_info['participants']) < party_info['max_size']:
                    party_info['participants'].add(member.id)
                else:
                    party_info['spectators'].add(member.id)
                
                await self.update_party_card(party_info)

        # 자유 파티 채널에서 나간 경우
        if before.channel and before.channel.id in self.active_parties:
            party_info = self.active_parties[before.channel.id]
            
            if member.id in party_info['participants']:
                party_info['participants'].remove(member.id)
            if member.id in party_info['spectators']:
                party_info['spectators'].remove(member.id)
            
            if party_info.get("party_card_message_id"):
                await self.update_party_card(party_info)
            
            await asyncio.sleep(0.5)
            channel = self.bot.get_channel(before.channel.id)
            if channel and not channel.members:
                # 파티 정리
                party_info = self.active_parties.pop(before.channel.id)
                
                if party_info["leader_id"] in self.setup_threads:
                    del self.setup_threads[party_info["leader_id"]]
                
                # 파티 카드 삭제
                if party_info.get("party_card_message_id"):
                    main_channel = self.bot.get_channel(self.bot.free_party_text_channel_id)
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
                
                await before.channel.delete(reason="자유 파티 채널에 사용자가 없음")

async def setup(bot: commands.Bot):
    await bot.add_cog(FreePartyManager(bot))