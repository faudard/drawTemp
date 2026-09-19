shader_type canvas_item;
render_mode unshaded;

uniform float grayscale_strength : hint_range(0.0, 1.0) = 0.96;
uniform float ink_strength : hint_range(0.0, 2.0) = 0.95;
uniform float poster_levels : hint_range(2.0, 10.0) = 5.0;
uniform float accent_strength : hint_range(0.0, 1.0) = 1.0;

float luma(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

float keep_accent(vec3 c) {
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float sat = mx - mn;

	float red = smoothstep(0.10, 0.32, c.r - max(c.g, c.b) * 0.90) * smoothstep(0.42, 0.68, c.r);
	float gold = smoothstep(0.46, 0.76, c.r) * smoothstep(0.28, 0.62, c.g) * (1.0 - smoothstep(0.34, 0.60, c.b));
	float green = smoothstep(0.15, 0.36, c.g - max(c.r, c.b) * 1.02) * smoothstep(0.48, 0.78, c.g);
	float accent = max(red, max(gold, green));
	return clamp(accent * smoothstep(0.18, 0.42, sat), 0.0, 1.0);
}

void fragment() {
	vec4 src = texture(TEXTURE, UV);
	if (src.a <= 0.001) {
		COLOR = src;
		return;
	}

	vec2 px = TEXTURE_PIXEL_SIZE;
	float lum = luma(src.rgb);
	float poster = floor(lum * poster_levels + 0.5) / poster_levels;

	float l1 = luma(texture(TEXTURE, UV + vec2(px.x, 0.0)).rgb);
	float l2 = luma(texture(TEXTURE, UV - vec2(px.x, 0.0)).rgb);
	float l3 = luma(texture(TEXTURE, UV + vec2(0.0, px.y)).rgb);
	float l4 = luma(texture(TEXTURE, UV - vec2(0.0, px.y)).rgb);
	float edge = clamp((abs(l1 - l2) + abs(l3 - l4)) * 4.8 * ink_strength, 0.0, 0.82);

	vec3 mono = vec3(clamp(poster - edge, 0.0, 1.0));
	float preserve = keep_accent(src.rgb) * accent_strength;
	vec3 selective = mix(mono, src.rgb, preserve);
	vec3 result = mix(src.rgb, selective, grayscale_strength);

	COLOR = vec4(result, src.a);
}
