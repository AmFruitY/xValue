interface HeroPlayerAvatarProps {
  initials: string;
  playerName: string;
}

export function HeroPlayerAvatar({
  initials,
  playerName,
}: HeroPlayerAvatarProps) {
  return (
    <div
      className="hero-avatar-shell mx-auto"
      role="img"
      aria-label={`Abstract avatar for ${playerName}`}
    >
      <div className="avatar-field" aria-hidden="true">
        <span className="avatar-arc" />
        <span className="avatar-data-axis" />
      </div>

      <div className="player-figure" aria-hidden="true">
        <div className="player-head" />
        <div className="player-neck" />
        <div className="player-jersey">
          <span className="player-shoulder-line" />
          <span className="avatar-initials">{initials}</span>
          <span className="jersey-accent" />
        </div>
      </div>
    </div>
  );
}
