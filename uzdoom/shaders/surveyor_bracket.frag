#version 330 core
// Argon concept; Codex review: exact rectangular aim protection, bounded
// controls/color/UVs, faint edge addition. Five texture reads at most.
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_world;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_strength;
uniform float u_progress;
uniform float u_active;

void main() {
    vec2 uv = clamp(v_uv, vec2(0.0), vec2(1.0));
    vec4 base = texture(u_world, uv);
    float strength = clamp(u_strength, 0.0, 1.0) * clamp(u_active, 0.0, 1.0);
    float progress = clamp(u_progress, 0.0, 1.0);
    vec2 distance_from_aim = abs(uv - 0.5);
    float peripheral = smoothstep(0.10, 0.18, max(distance_from_aim.x, distance_from_aim.y));
    if (strength <= 0.0 || peripheral <= 0.0) {
        fragColor = base;
        return;
    }
    vec2 size = max(u_resolution, vec2(1.0));
    vec2 texel = 1.0 / size;
    vec2 lower = 0.5 * texel;
    vec2 upper = 1.0 - lower;
    float edge_position = mix(0.025, 0.34, progress);
    float thickness = max(1.0 / size.x, 0.0015);
    float side = min(uv.x, 1.0 - uv.x);
    float line = 1.0 - smoothstep(thickness, 2.0 * thickness, abs(side - edge_position));
    float vertical = smoothstep(0.18, 0.23, uv.y) * (1.0 - smoothstep(0.77, 0.82, uv.y));
    float outside = 1.0 - smoothstep(edge_position, edge_position + 0.02, side);
    vec3 color = base.rgb;
    if (outside > 0.0) {
        vec3 n = texture(u_world, clamp(uv + vec2(0.0, texel.y), lower, upper)).rgb;
        vec3 s = texture(u_world, clamp(uv - vec2(0.0, texel.y), lower, upper)).rgb;
        vec3 e = texture(u_world, clamp(uv + vec2(texel.x, 0.0), lower, upper)).rgb;
        vec3 w = texture(u_world, clamp(uv - vec2(texel.x, 0.0), lower, upper)).rgb;
        float edge = clamp(dot(abs(n - s) + abs(e - w), vec3(1.0 / 3.0)), 0.0, 1.0);
        color += vec3(0.03, 0.22, 0.11) * edge * outside * peripheral * strength;
    }
    vec3 warning = mix(vec3(0.95, 0.62, 0.16), vec3(0.92, 0.25, 0.16), smoothstep(0.75, 1.0, progress));
    color = mix(color, warning, line * vertical * peripheral * strength * 0.65);
    fragColor = vec4(clamp(color, 0.0, 1.0), base.a);
}
