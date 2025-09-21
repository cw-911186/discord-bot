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
    def __init__(self, bot, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.selected_mode = None
        self.selected_size = None

    # ... (select 메뉴들은 내용 동일) ...
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
        await interaction.response.defer()

    @ui.select(
        placeholder="파티 인원 수를 선택하세요...",
        options=[
            discord.SelectOption(label="2인", value="2"), discord.SelectOption(label="3인", value="3"),
            discord.SelectOption(label="4인", value="4"), discord.SelectOption(label="5인", value="5"),
            discord.SelectOption(label="16인", value="16"),
        ]
    )
    async def size_select(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_size = int(select.values[0])
        await interaction.response.defer()

    @ui.button(label="🎉 파티 생성", style=discord.ButtonStyle.primary)
    async def create_party_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❗ 파티 생성자만 버튼을 누를 수 있습니다.", ephemeral=True)
        
        if not self.selected_mode or not self.selected_size:
            return await interaction.response.send_message("❗ 게임 모드와 인원 수를 모두 선택해야 합니다.", ephemeral=True)

        await interaction.response.defer()

        cog = self.bot.get_cog('PartyManager')
        if not cog or not self.author.voice: return
        
        party_vc = self.author.voice.channel
        
        party_info = cog.active_parties.get(party_vc.id)
        if not party_info: return
        party_info.update({
            "game_mode": self.selected_mode,
            "max_size": self.selected_size,
        })
        party_info["participants"].add(self.author.id)

        # 짧은 이름 추출
        short_name = cog.get_short_name(self.author.display_name)

        # 채널 이름 변경
        await party_vc.edit(name=f"{short_name}님의 파티")

        # 파티 카드 생성
        embed = discord.Embed(title=f"🎉 {short_name}님의 파티가 열렸습니다!", color=discord.Color.blue())
        embed.add_field(name="🕹️ 게임 모드", value=self.selected_mode, inline=False)
        embed.add_field(name="📊 현재 인원", value=f"1 / {self.selected_size}", inline=False)
        embed.add_field(name="👥 참가자 목록", value=short_name, inline=True)
        embed.add_field(name="👀 관전자 목록", value="없음", inline=True)
        embed.set_footer(text=f"음성 채널: {short_name}님의 파티")

        party_card_view = PartyCardView(self.bot, party_vc.id)
        party_card_msg = await interaction.channel.send(embed=embed, view=party_card_view)
        party_info["party_card_message_id"] = party_card_msg.id
        
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        if self.author.voice and "도우미" in self.author.voice.channel.name:
            await self.author.voice.channel.delete(reason="파티 생성 시간 초과")


# --- Cog 클래스 ---
class PartyManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_parties = {}
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
        if after.channel and after.channel.id == trigger_channel_id:
            category = after.channel.category
            
            # 짧은 이름 추출
            short_name = self.get_short_name(member.display_name)
            
            temp_vc = await category.create_voice_channel(name=f"{short_name}님의 파티설정 도우미")
            await member.move_to(temp_vc)

            text_channel = self.bot.get_channel(self.bot.party_text_channel_id)
            if text_channel:
                embed = discord.Embed(title="🎈 파티 생성 도우미", description=f"{member.mention}님, 파티 정보를 설정해주세요.", color=0x7289da)
                setup_view = PartySetupView(self.bot, member)
                setup_msg = await text_channel.send(embed=embed, view=setup_view)

                self.active_parties[temp_vc.id] = {
                    "leader_id": member.id,
                    "setup_message_id": setup_msg.id,
                    "party_card_message_id": None,
                    "game_mode": None, "max_size": 0,
                    "participants": set(), "spectators": set()
                }

        if before.channel and before.channel.id in self.active_parties:
            # 채널 업데이트 0.5초 대기 (멤버 수 즉시 반영을 위해)
            await asyncio.sleep(0.5)
            # 채널 객체를 다시 가져와 정확한 멤버 수를 확인
            channel = self.bot.get_channel(before.channel.id)
            if channel and not channel.members:
                party_info = self.active_parties.pop(before.channel.id)
                
                if party_info.get("party_card_message_id"):
                    text_channel = self.bot.get_channel(self.bot.party_text_channel_id)
                    try:
                        msg = await text_channel.fetch_message(party_info["party_card_message_id"])
                        await msg.delete()
                    except discord.NotFound:
                        pass
                
                await before.channel.delete(reason="파티 채널에 사용자가 없음")

async def setup(bot: commands.Bot):
    await bot.add_cog(PartyManager(bot))

