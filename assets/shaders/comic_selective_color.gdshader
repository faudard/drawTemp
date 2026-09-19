shader_type canvas_item;
render_mode unshaded;

uniform sampler2D screen_texture : hint_screen_texture, filter_linear;
uniform float grayscale_strength : hint_range(0.0, 1.0) = 0.94;
uniform float ink_strength : hint_range(0.0, 2.0) = 0.72;
uniform float poster_levels : hint_range(2.0, 12.0) = 6.0;
uniform float grain_strength : hint_range(0.0, 0.12) = 0.022;
uniform float selective_color_strength : hint_range(0.0, 1.0) = 1.0;\nuniform float halftone_strength : hint_range(0.0, 0.35) = 0.11;\nuniform float halftone_scale : hint_range(2.0, 10.0) = 4.0;

float luma(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float keep_color(vec3 c) {
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float sat = mx - mn;

	float red = smoothstep(0.10, 0.34, c.r - max(c.g, c.b) * 0.92) * smoothstep(0.36, 0.66, c.r);
	float gold = smoothstep(0.40, 0.72, c.r) * smoothstep(0.28, 0.62, c.g) * (1.0 - smoothstep(0.32, 0.58, c.b));
	float green = smoothstep(0.08, 0.28, c.g - max(c.r, c.b) * 1.02) * smoothstep(0.46, 0.72, c.g);
	float purple = smoothstep(0.06, 0.24, min(c.r, c.b) - c.g * 0.92) * smoothstep(0.34, 0.62, max(c.r, c.b));
	float cyan = smoothstep(0.04, 0.20, min(c.g, c.b) - c.r * 0.92) * smoothstep(0.44, 0.70, max(c.g, c.b));

	float accent = max(max(red, gold), max(green, max(purple, cyan)));
	accent *= smoothstep(0.14, 0.38, sat);
	return clamp(accent, 0.0, 1.0);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 px = SCREEN_PIXEL_SIZE;

	vec3 src = texture(screen_texture, uv).rgb;
	float lum = luma(src);
	float poster = floor(lum * poster_levels + 0.5) / poster_levels;

	float l1 = luma(texture(screen_texture, uv + vec2(px.x, 0.0)).rgb);
	float l2 = luma(texture(screen_texture, uv - vec2(px.x, 0.0)).rgb);
	float l3 = luma(texture(screen_texture, uv + vec2(0.0, px.y)).rgb);
	float l4 = luma(texture(screen_texture, uv - vec2(0.0, px.y)).rgb);
	float edge = abs(l1 - l2) + abs(l3 - l4);
	float ink = clamp(edge * 4.5 * ink_strength, 0.0, 0.86);

	float grain = (hash21(FRAGCOORD.xy) - 0.5) * grain_strength;
	vec3 mono = vec3(clamp(poster - ink + grain, 0.0, 1.0));

	float preserve = keep_color(src) * selective_color_strength;
	vec3 colored = mix(mono, src, preserve);
	vec3 final_color = mix(src, colored, grayscale_strength);

	COLOR = vec4(final_color, 1.0);
}
