#version 330 core
// Argon concept; Codex review: rectangular aim mask, bounded controls/UVs,
// continuous strength, source alpha. Two texture reads at most.
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
    float peripheral = smoothstep(0.10, 0.20, max(distance_from_aim.x, distance_from_aim.y));
    float amount = strength * progress * peripheral;
    if (amount <= 0.0) {
        fragColor = base;
        return;
    }
    vec2 size = max(u_resolution, vec2(1.0));
    vec2 half_texel = 0.5 / size;
    float block = mix(1.0, 8.0, strength * progress);
    vec2 quantized = (floor(uv * size / block) + 0.5) * block / size;
    vec2 sample_uv = clamp(mix(uv, quantized, amount), half_texel, 1.0 - half_texel);
    vec3 color = texture(u_world, sample_uv).rgb;
    float luma = dot(color, vec3(0.299, 0.587, 0.114));
    vec3 cool_gray = vec3(luma) * vec3(0.90, 0.95, 1.0);
    color = mix(color, cool_gray, 0.35 * amount);
    fragColor = vec4(clamp(color, 0.0, 1.0), base.a);
}
