//#region \0rolldown/runtime.js
var e = Object.create, t = Object.defineProperty, n = Object.getOwnPropertyDescriptor, r = Object.getOwnPropertyNames, i = Object.getPrototypeOf, a = Object.prototype.hasOwnProperty, o = (e, t) => () => (e && (t = e(e = 0)), t), s = (e, t) => () => (t || e((t = { exports: {} }).exports, t), t.exports), c = (e, n) => {
	let r = {};
	for (var i in e) t(r, i, {
		get: e[i],
		enumerable: !0
	});
	return n || t(r, Symbol.toStringTag, { value: "Module" }), r;
}, l = (e, i, o, s) => {
	if (i && typeof i == "object" || typeof i == "function") for (var c = r(i), l = 0, u = c.length, d; l < u; l++) d = c[l], !a.call(e, d) && d !== o && t(e, d, {
		get: ((e) => i[e]).bind(null, d),
		enumerable: !(s = n(i, d)) || s.enumerable
	});
	return e;
}, u = (n, r, a) => (a = n == null ? {} : e(i(n)), l(r || !n || !n.__esModule ? t(a, "default", {
	value: n,
	enumerable: !0
}) : a, n)), d = (e) => a.call(e, "module.exports") ? e["module.exports"] : l(t({}, "__esModule", { value: !0 }), e), f = /* @__PURE__ */ s(((e) => {
	Object.defineProperty(e, "__esModule", { value: !0 }), e.bech32m = e.bech32 = void 0;
	var t = "qpzry9x8gf2tvdw0s3jn54khce6mua7l", n = {};
	for (let e = 0; e < 32; e++) {
		let r = t.charAt(e);
		n[r] = e;
	}
	function r(e) {
		let t = e >> 25;
		return (e & 33554431) << 5 ^ -(t >> 0 & 1) & 996825010 ^ -(t >> 1 & 1) & 642813549 ^ -(t >> 2 & 1) & 513874426 ^ -(t >> 3 & 1) & 1027748829 ^ -(t >> 4 & 1) & 705979059;
	}
	function i(e) {
		let t = 1;
		for (let n = 0; n < e.length; ++n) {
			let i = e.charCodeAt(n);
			if (i < 33 || i > 126) return "Invalid prefix (" + e + ")";
			t = r(t) ^ i >> 5;
		}
		t = r(t);
		for (let n = 0; n < e.length; ++n) {
			let i = e.charCodeAt(n);
			t = r(t) ^ i & 31;
		}
		return t;
	}
	function a(e, t, n, r) {
		let i = 0, a = 0, o = (1 << n) - 1, s = [];
		for (let r = 0; r < e.length; ++r) for (i = i << t | e[r], a += t; a >= n;) a -= n, s.push(i >> a & o);
		if (r) a > 0 && s.push(i << n - a & o);
		else {
			if (a >= t) return "Excess padding";
			if (i << n - a & o) return "Non-zero padding";
		}
		return s;
	}
	function o(e) {
		return a(e, 8, 5, !0);
	}
	function s(e) {
		let t = a(e, 5, 8, !1);
		if (Array.isArray(t)) return t;
	}
	function c(e) {
		let t = a(e, 5, 8, !1);
		if (Array.isArray(t)) return t;
		throw Error(t);
	}
	function l(e) {
		let a;
		a = e === "bech32" ? 1 : 734539939;
		function l(e, n, o) {
			if (o ||= 90, e.length + 7 + n.length > o) throw TypeError("Exceeds length limit");
			e = e.toLowerCase();
			let s = i(e);
			if (typeof s == "string") throw Error(s);
			let c = e + "1";
			for (let e = 0; e < n.length; ++e) {
				let i = n[e];
				if (i >> 5) throw Error("Non 5-bit word");
				s = r(s) ^ i, c += t.charAt(i);
			}
			for (let e = 0; e < 6; ++e) s = r(s);
			s ^= a;
			for (let e = 0; e < 6; ++e) {
				let n = s >> (5 - e) * 5 & 31;
				c += t.charAt(n);
			}
			return c;
		}
		function u(e, t) {
			if (t ||= 90, e.length < 8) return e + " too short";
			if (e.length > t) return "Exceeds length limit";
			let o = e.toLowerCase(), s = e.toUpperCase();
			if (e !== o && e !== s) return "Mixed-case string " + e;
			e = o;
			let c = e.lastIndexOf("1");
			if (c === -1) return "No separator character for " + e;
			if (c === 0) return "Missing prefix for " + e;
			let l = e.slice(0, c), u = e.slice(c + 1);
			if (u.length < 6) return "Data too short";
			let d = i(l);
			if (typeof d == "string") return d;
			let f = [];
			for (let e = 0; e < u.length; ++e) {
				let t = u.charAt(e), i = n[t];
				if (i === void 0) return "Unknown character " + t;
				d = r(d) ^ i, !(e + 6 >= u.length) && f.push(i);
			}
			return d === a ? {
				prefix: l,
				words: f
			} : "Invalid checksum for " + e;
		}
		function d(e, t) {
			let n = u(e, t);
			if (typeof n == "object") return n;
		}
		function f(e, t) {
			let n = u(e, t);
			if (typeof n == "object") return n;
			throw Error(n);
		}
		return {
			decodeUnsafe: d,
			decode: f,
			encode: l,
			toWords: o,
			fromWordsUnsafe: s,
			fromWords: c
		};
	}
	e.bech32 = l("bech32"), e.bech32m = l("bech32m");
})), p = /* @__PURE__ */ s(((e) => {
	e.byteLength = c, e.toByteArray = u, e.fromByteArray = p;
	for (var t = [], n = [], r = typeof Uint8Array < "u" ? Uint8Array : Array, i = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", a = 0, o = i.length; a < o; ++a) t[a] = i[a], n[i.charCodeAt(a)] = a;
	n[45] = 62, n[95] = 63;
	function s(e) {
		var t = e.length;
		if (t % 4 > 0) throw Error("Invalid string. Length must be a multiple of 4");
		var n = e.indexOf("=");
		n === -1 && (n = t);
		var r = n === t ? 0 : 4 - n % 4;
		return [n, r];
	}
	function c(e) {
		var t = s(e), n = t[0], r = t[1];
		return (n + r) * 3 / 4 - r;
	}
	function l(e, t, n) {
		return (t + n) * 3 / 4 - n;
	}
	function u(e) {
		var t, i = s(e), a = i[0], o = i[1], c = new r(l(e, a, o)), u = 0, d = o > 0 ? a - 4 : a, f;
		for (f = 0; f < d; f += 4) t = n[e.charCodeAt(f)] << 18 | n[e.charCodeAt(f + 1)] << 12 | n[e.charCodeAt(f + 2)] << 6 | n[e.charCodeAt(f + 3)], c[u++] = t >> 16 & 255, c[u++] = t >> 8 & 255, c[u++] = t & 255;
		return o === 2 && (t = n[e.charCodeAt(f)] << 2 | n[e.charCodeAt(f + 1)] >> 4, c[u++] = t & 255), o === 1 && (t = n[e.charCodeAt(f)] << 10 | n[e.charCodeAt(f + 1)] << 4 | n[e.charCodeAt(f + 2)] >> 2, c[u++] = t >> 8 & 255, c[u++] = t & 255), c;
	}
	function d(e) {
		return t[e >> 18 & 63] + t[e >> 12 & 63] + t[e >> 6 & 63] + t[e & 63];
	}
	function f(e, t, n) {
		for (var r, i = [], a = t; a < n; a += 3) r = (e[a] << 16 & 16711680) + (e[a + 1] << 8 & 65280) + (e[a + 2] & 255), i.push(d(r));
		return i.join("");
	}
	function p(e) {
		for (var n, r = e.length, i = r % 3, a = [], o = 16383, s = 0, c = r - i; s < c; s += o) a.push(f(e, s, s + o > c ? c : s + o));
		return i === 1 ? (n = e[r - 1], a.push(t[n >> 2] + t[n << 4 & 63] + "==")) : i === 2 && (n = (e[r - 2] << 8) + e[r - 1], a.push(t[n >> 10] + t[n >> 4 & 63] + t[n << 2 & 63] + "=")), a.join("");
	}
})), m = /* @__PURE__ */ s(((e) => {
	e.read = function(e, t, n, r, i) {
		var a, o, s = i * 8 - r - 1, c = (1 << s) - 1, l = c >> 1, u = -7, d = n ? i - 1 : 0, f = n ? -1 : 1, p = e[t + d];
		for (d += f, a = p & (1 << -u) - 1, p >>= -u, u += s; u > 0; a = a * 256 + e[t + d], d += f, u -= 8);
		for (o = a & (1 << -u) - 1, a >>= -u, u += r; u > 0; o = o * 256 + e[t + d], d += f, u -= 8);
		if (a === 0) a = 1 - l;
		else if (a === c) return o ? NaN : (p ? -1 : 1) * Infinity;
		else o += 2 ** r, a -= l;
		return (p ? -1 : 1) * o * 2 ** (a - r);
	}, e.write = function(e, t, n, r, i, a) {
		var o, s, c, l = a * 8 - i - 1, u = (1 << l) - 1, d = u >> 1, f = i === 23 ? 2 ** -24 - 2 ** -77 : 0, p = r ? 0 : a - 1, m = r ? 1 : -1, h = t < 0 || t === 0 && 1 / t < 0 ? 1 : 0;
		for (t = Math.abs(t), isNaN(t) || t === Infinity ? (s = isNaN(t) ? 1 : 0, o = u) : (o = Math.floor(Math.log(t) / Math.LN2), t * (c = 2 ** -o) < 1 && (o--, c *= 2), o + d >= 1 ? t += f / c : t += f * 2 ** (1 - d), t * c >= 2 && (o++, c /= 2), o + d >= u ? (s = 0, o = u) : o + d >= 1 ? (s = (t * c - 1) * 2 ** i, o += d) : (s = t * 2 ** (d - 1) * 2 ** i, o = 0)); i >= 8; e[n + p] = s & 255, p += m, s /= 256, i -= 8);
		for (o = o << i | s, l += i; l > 0; e[n + p] = o & 255, p += m, o /= 256, l -= 8);
		e[n + p - m] |= h * 128;
	};
})), h = (/* @__PURE__ */ s(((e) => {
	var t = p(), n = m(), r = typeof Symbol == "function" && typeof Symbol.for == "function" ? Symbol.for("nodejs.util.inspect.custom") : null;
	e.Buffer = s, e.SlowBuffer = b, e.INSPECT_MAX_BYTES = 50;
	var i = 2147483647;
	e.kMaxLength = i, s.TYPED_ARRAY_SUPPORT = a(), !s.TYPED_ARRAY_SUPPORT && typeof console < "u" && typeof console.error == "function" && console.error("This browser lacks typed array (Uint8Array) support which is required by `buffer` v5.x. Use `buffer` v4.x if you require old browser support.");
	function a() {
		try {
			let e = new Uint8Array(1), t = { foo: function() {
				return 42;
			} };
			return Object.setPrototypeOf(t, Uint8Array.prototype), Object.setPrototypeOf(e, t), e.foo() === 42;
		} catch {
			return !1;
		}
	}
	Object.defineProperty(s.prototype, "parent", {
		enumerable: !0,
		get: function() {
			if (s.isBuffer(this)) return this.buffer;
		}
	}), Object.defineProperty(s.prototype, "offset", {
		enumerable: !0,
		get: function() {
			if (s.isBuffer(this)) return this.byteOffset;
		}
	});
	function o(e) {
		if (e > i) throw RangeError("The value \"" + e + "\" is invalid for option \"size\"");
		let t = new Uint8Array(e);
		return Object.setPrototypeOf(t, s.prototype), t;
	}
	function s(e, t, n) {
		if (typeof e == "number") {
			if (typeof t == "string") throw TypeError("The \"string\" argument must be of type string. Received type number");
			return d(e);
		}
		return c(e, t, n);
	}
	s.poolSize = 8192;
	function c(e, t, n) {
		if (typeof e == "string") return f(e, t);
		if (ArrayBuffer.isView(e)) return g(e);
		if (e == null) throw TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof e);
		if (U(e, ArrayBuffer) || e && U(e.buffer, ArrayBuffer) || typeof SharedArrayBuffer < "u" && (U(e, SharedArrayBuffer) || e && U(e.buffer, SharedArrayBuffer))) return _(e, t, n);
		if (typeof e == "number") throw TypeError("The \"value\" argument must not be of type number. Received type number");
		let r = e.valueOf && e.valueOf();
		if (r != null && r !== e) return s.from(r, t, n);
		let i = v(e);
		if (i) return i;
		if (typeof Symbol < "u" && Symbol.toPrimitive != null && typeof e[Symbol.toPrimitive] == "function") return s.from(e[Symbol.toPrimitive]("string"), t, n);
		throw TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, or Array-like Object. Received type " + typeof e);
	}
	s.from = function(e, t, n) {
		return c(e, t, n);
	}, Object.setPrototypeOf(s.prototype, Uint8Array.prototype), Object.setPrototypeOf(s, Uint8Array);
	function l(e) {
		if (typeof e != "number") throw TypeError("\"size\" argument must be of type number");
		if (e < 0) throw RangeError("The value \"" + e + "\" is invalid for option \"size\"");
	}
	function u(e, t, n) {
		return l(e), e <= 0 || t === void 0 ? o(e) : typeof n == "string" ? o(e).fill(t, n) : o(e).fill(t);
	}
	s.alloc = function(e, t, n) {
		return u(e, t, n);
	};
	function d(e) {
		return l(e), o(e < 0 ? 0 : y(e) | 0);
	}
	s.allocUnsafe = function(e) {
		return d(e);
	}, s.allocUnsafeSlow = function(e) {
		return d(e);
	};
	function f(e, t) {
		if ((typeof t != "string" || t === "") && (t = "utf8"), !s.isEncoding(t)) throw TypeError("Unknown encoding: " + t);
		let n = x(e, t) | 0, r = o(n), i = r.write(e, t);
		return i !== n && (r = r.slice(0, i)), r;
	}
	function h(e) {
		let t = e.length < 0 ? 0 : y(e.length) | 0, n = o(t);
		for (let r = 0; r < t; r += 1) n[r] = e[r] & 255;
		return n;
	}
	function g(e) {
		if (U(e, Uint8Array)) {
			let t = new Uint8Array(e);
			return _(t.buffer, t.byteOffset, t.byteLength);
		}
		return h(e);
	}
	function _(e, t, n) {
		if (t < 0 || e.byteLength < t) throw RangeError("\"offset\" is outside of buffer bounds");
		if (e.byteLength < t + (n || 0)) throw RangeError("\"length\" is outside of buffer bounds");
		let r;
		return r = t === void 0 && n === void 0 ? new Uint8Array(e) : n === void 0 ? new Uint8Array(e, t) : new Uint8Array(e, t, n), Object.setPrototypeOf(r, s.prototype), r;
	}
	function v(e) {
		if (s.isBuffer(e)) {
			let t = y(e.length) | 0, n = o(t);
			return n.length === 0 || e.copy(n, 0, 0, t), n;
		}
		if (e.length !== void 0) return typeof e.length != "number" || _e(e.length) ? o(0) : h(e);
		if (e.type === "Buffer" && Array.isArray(e.data)) return h(e.data);
	}
	function y(e) {
		if (e >= i) throw RangeError("Attempt to allocate Buffer larger than maximum size: 0x" + i.toString(16) + " bytes");
		return e | 0;
	}
	function b(e) {
		return +e != e && (e = 0), s.alloc(+e);
	}
	s.isBuffer = function(e) {
		return e != null && e._isBuffer === !0 && e !== s.prototype;
	}, s.compare = function(e, t) {
		if (U(e, Uint8Array) && (e = s.from(e, e.offset, e.byteLength)), U(t, Uint8Array) && (t = s.from(t, t.offset, t.byteLength)), !s.isBuffer(e) || !s.isBuffer(t)) throw TypeError("The \"buf1\", \"buf2\" arguments must be one of type Buffer or Uint8Array");
		if (e === t) return 0;
		let n = e.length, r = t.length;
		for (let i = 0, a = Math.min(n, r); i < a; ++i) if (e[i] !== t[i]) {
			n = e[i], r = t[i];
			break;
		}
		return n < r ? -1 : r < n ? 1 : 0;
	}, s.isEncoding = function(e) {
		switch (String(e).toLowerCase()) {
			case "hex":
			case "utf8":
			case "utf-8":
			case "ascii":
			case "latin1":
			case "binary":
			case "base64":
			case "ucs2":
			case "ucs-2":
			case "utf16le":
			case "utf-16le": return !0;
			default: return !1;
		}
	}, s.concat = function(e, t) {
		if (!Array.isArray(e)) throw TypeError("\"list\" argument must be an Array of Buffers");
		if (e.length === 0) return s.alloc(0);
		let n;
		if (t === void 0) for (t = 0, n = 0; n < e.length; ++n) t += e[n].length;
		let r = s.allocUnsafe(t), i = 0;
		for (n = 0; n < e.length; ++n) {
			let t = e[n];
			if (U(t, Uint8Array)) i + t.length > r.length ? (s.isBuffer(t) || (t = s.from(t)), t.copy(r, i)) : Uint8Array.prototype.set.call(r, t, i);
			else if (s.isBuffer(t)) t.copy(r, i);
			else throw TypeError("\"list\" argument must be an Array of Buffers");
			i += t.length;
		}
		return r;
	};
	function x(e, t) {
		if (s.isBuffer(e)) return e.length;
		if (ArrayBuffer.isView(e) || U(e, ArrayBuffer)) return e.byteLength;
		if (typeof e != "string") throw TypeError("The \"string\" argument must be one of type string, Buffer, or ArrayBuffer. Received type " + typeof e);
		let n = e.length, r = arguments.length > 2 && arguments[2] === !0;
		if (!r && n === 0) return 0;
		let i = !1;
		for (;;) switch (t) {
			case "ascii":
			case "latin1":
			case "binary": return n;
			case "utf8":
			case "utf-8": return me(e).length;
			case "ucs2":
			case "ucs-2":
			case "utf16le":
			case "utf-16le": return n * 2;
			case "hex": return n >>> 1;
			case "base64": return ge(e).length;
			default:
				if (i) return r ? -1 : me(e).length;
				t = ("" + t).toLowerCase(), i = !0;
		}
	}
	s.byteLength = x;
	function S(e, t, n) {
		let r = !1;
		if ((t === void 0 || t < 0) && (t = 0), t > this.length || ((n === void 0 || n > this.length) && (n = this.length), n <= 0) || (n >>>= 0, t >>>= 0, n <= t)) return "";
		for (e ||= "utf8";;) switch (e) {
			case "hex": return re(this, t, n);
			case "utf8":
			case "utf-8": return A(this, t, n);
			case "ascii": return M(this, t, n);
			case "latin1":
			case "binary": return N(this, t, n);
			case "base64": return te(this, t, n);
			case "ucs2":
			case "ucs-2":
			case "utf16le":
			case "utf-16le": return ie(this, t, n);
			default:
				if (r) throw TypeError("Unknown encoding: " + e);
				e = (e + "").toLowerCase(), r = !0;
		}
	}
	s.prototype._isBuffer = !0;
	function C(e, t, n) {
		let r = e[t];
		e[t] = e[n], e[n] = r;
	}
	s.prototype.swap16 = function() {
		let e = this.length;
		if (e % 2 != 0) throw RangeError("Buffer size must be a multiple of 16-bits");
		for (let t = 0; t < e; t += 2) C(this, t, t + 1);
		return this;
	}, s.prototype.swap32 = function() {
		let e = this.length;
		if (e % 4 != 0) throw RangeError("Buffer size must be a multiple of 32-bits");
		for (let t = 0; t < e; t += 4) C(this, t, t + 3), C(this, t + 1, t + 2);
		return this;
	}, s.prototype.swap64 = function() {
		let e = this.length;
		if (e % 8 != 0) throw RangeError("Buffer size must be a multiple of 64-bits");
		for (let t = 0; t < e; t += 8) C(this, t, t + 7), C(this, t + 1, t + 6), C(this, t + 2, t + 5), C(this, t + 3, t + 4);
		return this;
	}, s.prototype.toString = function() {
		let e = this.length;
		return e === 0 ? "" : arguments.length === 0 ? A(this, 0, e) : S.apply(this, arguments);
	}, s.prototype.toLocaleString = s.prototype.toString, s.prototype.equals = function(e) {
		if (!s.isBuffer(e)) throw TypeError("Argument must be a Buffer");
		return this === e ? !0 : s.compare(this, e) === 0;
	}, s.prototype.inspect = function() {
		let t = "", n = e.INSPECT_MAX_BYTES;
		return t = this.toString("hex", 0, n).replace(/(.{2})/g, "$1 ").trim(), this.length > n && (t += " ... "), "<Buffer " + t + ">";
	}, r && (s.prototype[r] = s.prototype.inspect), s.prototype.compare = function(e, t, n, r, i) {
		if (U(e, Uint8Array) && (e = s.from(e, e.offset, e.byteLength)), !s.isBuffer(e)) throw TypeError("The \"target\" argument must be one of type Buffer or Uint8Array. Received type " + typeof e);
		if (t === void 0 && (t = 0), n === void 0 && (n = e ? e.length : 0), r === void 0 && (r = 0), i === void 0 && (i = this.length), t < 0 || n > e.length || r < 0 || i > this.length) throw RangeError("out of range index");
		if (r >= i && t >= n) return 0;
		if (r >= i) return -1;
		if (t >= n) return 1;
		if (t >>>= 0, n >>>= 0, r >>>= 0, i >>>= 0, this === e) return 0;
		let a = i - r, o = n - t, c = Math.min(a, o), l = this.slice(r, i), u = e.slice(t, n);
		for (let e = 0; e < c; ++e) if (l[e] !== u[e]) {
			a = l[e], o = u[e];
			break;
		}
		return a < o ? -1 : o < a ? 1 : 0;
	};
	function w(e, t, n, r, i) {
		if (e.length === 0) return -1;
		if (typeof n == "string" ? (r = n, n = 0) : n > 2147483647 ? n = 2147483647 : n < -2147483648 && (n = -2147483648), n = +n, _e(n) && (n = i ? 0 : e.length - 1), n < 0 && (n = e.length + n), n >= e.length) {
			if (i) return -1;
			n = e.length - 1;
		} else if (n < 0) if (i) n = 0;
		else return -1;
		if (typeof t == "string" && (t = s.from(t, r)), s.isBuffer(t)) return t.length === 0 ? -1 : T(e, t, n, r, i);
		if (typeof t == "number") return t &= 255, typeof Uint8Array.prototype.indexOf == "function" ? i ? Uint8Array.prototype.indexOf.call(e, t, n) : Uint8Array.prototype.lastIndexOf.call(e, t, n) : T(e, [t], n, r, i);
		throw TypeError("val must be string, number or Buffer");
	}
	function T(e, t, n, r, i) {
		let a = 1, o = e.length, s = t.length;
		if (r !== void 0 && (r = String(r).toLowerCase(), r === "ucs2" || r === "ucs-2" || r === "utf16le" || r === "utf-16le")) {
			if (e.length < 2 || t.length < 2) return -1;
			a = 2, o /= 2, s /= 2, n /= 2;
		}
		function c(e, t) {
			return a === 1 ? e[t] : e.readUInt16BE(t * a);
		}
		let l;
		if (i) {
			let r = -1;
			for (l = n; l < o; l++) if (c(e, l) === c(t, r === -1 ? 0 : l - r)) {
				if (r === -1 && (r = l), l - r + 1 === s) return r * a;
			} else r !== -1 && (l -= l - r), r = -1;
		} else for (n + s > o && (n = o - s), l = n; l >= 0; l--) {
			let n = !0;
			for (let r = 0; r < s; r++) if (c(e, l + r) !== c(t, r)) {
				n = !1;
				break;
			}
			if (n) return l;
		}
		return -1;
	}
	s.prototype.includes = function(e, t, n) {
		return this.indexOf(e, t, n) !== -1;
	}, s.prototype.indexOf = function(e, t, n) {
		return w(this, e, t, n, !0);
	}, s.prototype.lastIndexOf = function(e, t, n) {
		return w(this, e, t, n, !1);
	};
	function E(e, t, n, r) {
		n = Number(n) || 0;
		let i = e.length - n;
		r ? (r = Number(r), r > i && (r = i)) : r = i;
		let a = t.length;
		r > a / 2 && (r = a / 2);
		let o;
		for (o = 0; o < r; ++o) {
			let r = parseInt(t.substr(o * 2, 2), 16);
			if (_e(r)) return o;
			e[n + o] = r;
		}
		return o;
	}
	function D(e, t, n, r) {
		return H(me(t, e.length - n), e, n, r);
	}
	function ee(e, t, n, r) {
		return H(V(t), e, n, r);
	}
	function O(e, t, n, r) {
		return H(ge(t), e, n, r);
	}
	function k(e, t, n, r) {
		return H(he(t, e.length - n), e, n, r);
	}
	s.prototype.write = function(e, t, n, r) {
		if (t === void 0) r = "utf8", n = this.length, t = 0;
		else if (n === void 0 && typeof t == "string") r = t, n = this.length, t = 0;
		else if (isFinite(t)) t >>>= 0, isFinite(n) ? (n >>>= 0, r === void 0 && (r = "utf8")) : (r = n, n = void 0);
		else throw Error("Buffer.write(string, encoding, offset[, length]) is no longer supported");
		let i = this.length - t;
		if ((n === void 0 || n > i) && (n = i), e.length > 0 && (n < 0 || t < 0) || t > this.length) throw RangeError("Attempt to write outside buffer bounds");
		r ||= "utf8";
		let a = !1;
		for (;;) switch (r) {
			case "hex": return E(this, e, t, n);
			case "utf8":
			case "utf-8": return D(this, e, t, n);
			case "ascii":
			case "latin1":
			case "binary": return ee(this, e, t, n);
			case "base64": return O(this, e, t, n);
			case "ucs2":
			case "ucs-2":
			case "utf16le":
			case "utf-16le": return k(this, e, t, n);
			default:
				if (a) throw TypeError("Unknown encoding: " + r);
				r = ("" + r).toLowerCase(), a = !0;
		}
	}, s.prototype.toJSON = function() {
		return {
			type: "Buffer",
			data: Array.prototype.slice.call(this._arr || this, 0)
		};
	};
	function te(e, n, r) {
		return n === 0 && r === e.length ? t.fromByteArray(e) : t.fromByteArray(e.slice(n, r));
	}
	function A(e, t, n) {
		n = Math.min(e.length, n);
		let r = [], i = t;
		for (; i < n;) {
			let t = e[i], a = null, o = t > 239 ? 4 : t > 223 ? 3 : t > 191 ? 2 : 1;
			if (i + o <= n) {
				let n, r, s, c;
				switch (o) {
					case 1:
						t < 128 && (a = t);
						break;
					case 2:
						n = e[i + 1], (n & 192) == 128 && (c = (t & 31) << 6 | n & 63, c > 127 && (a = c));
						break;
					case 3:
						n = e[i + 1], r = e[i + 2], (n & 192) == 128 && (r & 192) == 128 && (c = (t & 15) << 12 | (n & 63) << 6 | r & 63, c > 2047 && (c < 55296 || c > 57343) && (a = c));
						break;
					case 4: n = e[i + 1], r = e[i + 2], s = e[i + 3], (n & 192) == 128 && (r & 192) == 128 && (s & 192) == 128 && (c = (t & 15) << 18 | (n & 63) << 12 | (r & 63) << 6 | s & 63, c > 65535 && c < 1114112 && (a = c));
				}
			}
			a === null ? (a = 65533, o = 1) : a > 65535 && (a -= 65536, r.push(a >>> 10 & 1023 | 55296), a = 56320 | a & 1023), r.push(a), i += o;
		}
		return ne(r);
	}
	var j = 4096;
	function ne(e) {
		let t = e.length;
		if (t <= j) return String.fromCharCode.apply(String, e);
		let n = "", r = 0;
		for (; r < t;) n += String.fromCharCode.apply(String, e.slice(r, r += j));
		return n;
	}
	function M(e, t, n) {
		let r = "";
		n = Math.min(e.length, n);
		for (let i = t; i < n; ++i) r += String.fromCharCode(e[i] & 127);
		return r;
	}
	function N(e, t, n) {
		let r = "";
		n = Math.min(e.length, n);
		for (let i = t; i < n; ++i) r += String.fromCharCode(e[i]);
		return r;
	}
	function re(e, t, n) {
		let r = e.length;
		(!t || t < 0) && (t = 0), (!n || n < 0 || n > r) && (n = r);
		let i = "";
		for (let r = t; r < n; ++r) i += ve[e[r]];
		return i;
	}
	function ie(e, t, n) {
		let r = e.slice(t, n), i = "";
		for (let e = 0; e < r.length - 1; e += 2) i += String.fromCharCode(r[e] + r[e + 1] * 256);
		return i;
	}
	s.prototype.slice = function(e, t) {
		let n = this.length;
		e = ~~e, t = t === void 0 ? n : ~~t, e < 0 ? (e += n, e < 0 && (e = 0)) : e > n && (e = n), t < 0 ? (t += n, t < 0 && (t = 0)) : t > n && (t = n), t < e && (t = e);
		let r = this.subarray(e, t);
		return Object.setPrototypeOf(r, s.prototype), r;
	};
	function P(e, t, n) {
		if (e % 1 != 0 || e < 0) throw RangeError("offset is not uint");
		if (e + t > n) throw RangeError("Trying to access beyond buffer length");
	}
	s.prototype.readUintLE = s.prototype.readUIntLE = function(e, t, n) {
		e >>>= 0, t >>>= 0, n || P(e, t, this.length);
		let r = this[e], i = 1, a = 0;
		for (; ++a < t && (i *= 256);) r += this[e + a] * i;
		return r;
	}, s.prototype.readUintBE = s.prototype.readUIntBE = function(e, t, n) {
		e >>>= 0, t >>>= 0, n || P(e, t, this.length);
		let r = this[e + --t], i = 1;
		for (; t > 0 && (i *= 256);) r += this[e + --t] * i;
		return r;
	}, s.prototype.readUint8 = s.prototype.readUInt8 = function(e, t) {
		return e >>>= 0, t || P(e, 1, this.length), this[e];
	}, s.prototype.readUint16LE = s.prototype.readUInt16LE = function(e, t) {
		return e >>>= 0, t || P(e, 2, this.length), this[e] | this[e + 1] << 8;
	}, s.prototype.readUint16BE = s.prototype.readUInt16BE = function(e, t) {
		return e >>>= 0, t || P(e, 2, this.length), this[e] << 8 | this[e + 1];
	}, s.prototype.readUint32LE = s.prototype.readUInt32LE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), (this[e] | this[e + 1] << 8 | this[e + 2] << 16) + this[e + 3] * 16777216;
	}, s.prototype.readUint32BE = s.prototype.readUInt32BE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), this[e] * 16777216 + (this[e + 1] << 16 | this[e + 2] << 8 | this[e + 3]);
	}, s.prototype.readBigUInt64LE = W(function(e) {
		e >>>= 0, B(e, "offset");
		let t = this[e], n = this[e + 7];
		(t === void 0 || n === void 0) && de(e, this.length - 8);
		let r = t + this[++e] * 2 ** 8 + this[++e] * 2 ** 16 + this[++e] * 2 ** 24, i = this[++e] + this[++e] * 2 ** 8 + this[++e] * 2 ** 16 + n * 2 ** 24;
		return BigInt(r) + (BigInt(i) << BigInt(32));
	}), s.prototype.readBigUInt64BE = W(function(e) {
		e >>>= 0, B(e, "offset");
		let t = this[e], n = this[e + 7];
		(t === void 0 || n === void 0) && de(e, this.length - 8);
		let r = t * 2 ** 24 + this[++e] * 2 ** 16 + this[++e] * 2 ** 8 + this[++e], i = this[++e] * 2 ** 24 + this[++e] * 2 ** 16 + this[++e] * 2 ** 8 + n;
		return (BigInt(r) << BigInt(32)) + BigInt(i);
	}), s.prototype.readIntLE = function(e, t, n) {
		e >>>= 0, t >>>= 0, n || P(e, t, this.length);
		let r = this[e], i = 1, a = 0;
		for (; ++a < t && (i *= 256);) r += this[e + a] * i;
		return i *= 128, r >= i && (r -= 2 ** (8 * t)), r;
	}, s.prototype.readIntBE = function(e, t, n) {
		e >>>= 0, t >>>= 0, n || P(e, t, this.length);
		let r = t, i = 1, a = this[e + --r];
		for (; r > 0 && (i *= 256);) a += this[e + --r] * i;
		return i *= 128, a >= i && (a -= 2 ** (8 * t)), a;
	}, s.prototype.readInt8 = function(e, t) {
		return e >>>= 0, t || P(e, 1, this.length), this[e] & 128 ? (255 - this[e] + 1) * -1 : this[e];
	}, s.prototype.readInt16LE = function(e, t) {
		e >>>= 0, t || P(e, 2, this.length);
		let n = this[e] | this[e + 1] << 8;
		return n & 32768 ? n | 4294901760 : n;
	}, s.prototype.readInt16BE = function(e, t) {
		e >>>= 0, t || P(e, 2, this.length);
		let n = this[e + 1] | this[e] << 8;
		return n & 32768 ? n | 4294901760 : n;
	}, s.prototype.readInt32LE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), this[e] | this[e + 1] << 8 | this[e + 2] << 16 | this[e + 3] << 24;
	}, s.prototype.readInt32BE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), this[e] << 24 | this[e + 1] << 16 | this[e + 2] << 8 | this[e + 3];
	}, s.prototype.readBigInt64LE = W(function(e) {
		e >>>= 0, B(e, "offset");
		let t = this[e], n = this[e + 7];
		(t === void 0 || n === void 0) && de(e, this.length - 8);
		let r = this[e + 4] + this[e + 5] * 2 ** 8 + this[e + 6] * 2 ** 16 + (n << 24);
		return (BigInt(r) << BigInt(32)) + BigInt(t + this[++e] * 2 ** 8 + this[++e] * 2 ** 16 + this[++e] * 2 ** 24);
	}), s.prototype.readBigInt64BE = W(function(e) {
		e >>>= 0, B(e, "offset");
		let t = this[e], n = this[e + 7];
		(t === void 0 || n === void 0) && de(e, this.length - 8);
		let r = (t << 24) + this[++e] * 2 ** 16 + this[++e] * 2 ** 8 + this[++e];
		return (BigInt(r) << BigInt(32)) + BigInt(this[++e] * 2 ** 24 + this[++e] * 2 ** 16 + this[++e] * 2 ** 8 + n);
	}), s.prototype.readFloatLE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), n.read(this, e, !0, 23, 4);
	}, s.prototype.readFloatBE = function(e, t) {
		return e >>>= 0, t || P(e, 4, this.length), n.read(this, e, !1, 23, 4);
	}, s.prototype.readDoubleLE = function(e, t) {
		return e >>>= 0, t || P(e, 8, this.length), n.read(this, e, !0, 52, 8);
	}, s.prototype.readDoubleBE = function(e, t) {
		return e >>>= 0, t || P(e, 8, this.length), n.read(this, e, !1, 52, 8);
	};
	function ae(e, t, n, r, i, a) {
		if (!s.isBuffer(e)) throw TypeError("\"buffer\" argument must be a Buffer instance");
		if (t > i || t < a) throw RangeError("\"value\" argument is out of bounds");
		if (n + r > e.length) throw RangeError("Index out of range");
	}
	s.prototype.writeUintLE = s.prototype.writeUIntLE = function(e, t, n, r) {
		if (e = +e, t >>>= 0, n >>>= 0, !r) {
			let r = 2 ** (8 * n) - 1;
			ae(this, e, t, n, r, 0);
		}
		let i = 1, a = 0;
		for (this[t] = e & 255; ++a < n && (i *= 256);) this[t + a] = e / i & 255;
		return t + n;
	}, s.prototype.writeUintBE = s.prototype.writeUIntBE = function(e, t, n, r) {
		if (e = +e, t >>>= 0, n >>>= 0, !r) {
			let r = 2 ** (8 * n) - 1;
			ae(this, e, t, n, r, 0);
		}
		let i = n - 1, a = 1;
		for (this[t + i] = e & 255; --i >= 0 && (a *= 256);) this[t + i] = e / a & 255;
		return t + n;
	}, s.prototype.writeUint8 = s.prototype.writeUInt8 = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 1, 255, 0), this[t] = e & 255, t + 1;
	}, s.prototype.writeUint16LE = s.prototype.writeUInt16LE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 2, 65535, 0), this[t] = e & 255, this[t + 1] = e >>> 8, t + 2;
	}, s.prototype.writeUint16BE = s.prototype.writeUInt16BE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 2, 65535, 0), this[t] = e >>> 8, this[t + 1] = e & 255, t + 2;
	}, s.prototype.writeUint32LE = s.prototype.writeUInt32LE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 4, 4294967295, 0), this[t + 3] = e >>> 24, this[t + 2] = e >>> 16, this[t + 1] = e >>> 8, this[t] = e & 255, t + 4;
	}, s.prototype.writeUint32BE = s.prototype.writeUInt32BE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 4, 4294967295, 0), this[t] = e >>> 24, this[t + 1] = e >>> 16, this[t + 2] = e >>> 8, this[t + 3] = e & 255, t + 4;
	};
	function F(e, t, n, r, i) {
		z(t, r, i, e, n, 7);
		let a = Number(t & BigInt(4294967295));
		e[n++] = a, a >>= 8, e[n++] = a, a >>= 8, e[n++] = a, a >>= 8, e[n++] = a;
		let o = Number(t >> BigInt(32) & BigInt(4294967295));
		return e[n++] = o, o >>= 8, e[n++] = o, o >>= 8, e[n++] = o, o >>= 8, e[n++] = o, n;
	}
	function oe(e, t, n, r, i) {
		z(t, r, i, e, n, 7);
		let a = Number(t & BigInt(4294967295));
		e[n + 7] = a, a >>= 8, e[n + 6] = a, a >>= 8, e[n + 5] = a, a >>= 8, e[n + 4] = a;
		let o = Number(t >> BigInt(32) & BigInt(4294967295));
		return e[n + 3] = o, o >>= 8, e[n + 2] = o, o >>= 8, e[n + 1] = o, o >>= 8, e[n] = o, n + 8;
	}
	s.prototype.writeBigUInt64LE = W(function(e, t = 0) {
		return F(this, e, t, BigInt(0), BigInt("0xffffffffffffffff"));
	}), s.prototype.writeBigUInt64BE = W(function(e, t = 0) {
		return oe(this, e, t, BigInt(0), BigInt("0xffffffffffffffff"));
	}), s.prototype.writeIntLE = function(e, t, n, r) {
		if (e = +e, t >>>= 0, !r) {
			let r = 2 ** (8 * n - 1);
			ae(this, e, t, n, r - 1, -r);
		}
		let i = 0, a = 1, o = 0;
		for (this[t] = e & 255; ++i < n && (a *= 256);) e < 0 && o === 0 && this[t + i - 1] !== 0 && (o = 1), this[t + i] = (e / a >> 0) - o & 255;
		return t + n;
	}, s.prototype.writeIntBE = function(e, t, n, r) {
		if (e = +e, t >>>= 0, !r) {
			let r = 2 ** (8 * n - 1);
			ae(this, e, t, n, r - 1, -r);
		}
		let i = n - 1, a = 1, o = 0;
		for (this[t + i] = e & 255; --i >= 0 && (a *= 256);) e < 0 && o === 0 && this[t + i + 1] !== 0 && (o = 1), this[t + i] = (e / a >> 0) - o & 255;
		return t + n;
	}, s.prototype.writeInt8 = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 1, 127, -128), e < 0 && (e = 255 + e + 1), this[t] = e & 255, t + 1;
	}, s.prototype.writeInt16LE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 2, 32767, -32768), this[t] = e & 255, this[t + 1] = e >>> 8, t + 2;
	}, s.prototype.writeInt16BE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 2, 32767, -32768), this[t] = e >>> 8, this[t + 1] = e & 255, t + 2;
	}, s.prototype.writeInt32LE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 4, 2147483647, -2147483648), this[t] = e & 255, this[t + 1] = e >>> 8, this[t + 2] = e >>> 16, this[t + 3] = e >>> 24, t + 4;
	}, s.prototype.writeInt32BE = function(e, t, n) {
		return e = +e, t >>>= 0, n || ae(this, e, t, 4, 2147483647, -2147483648), e < 0 && (e = 4294967295 + e + 1), this[t] = e >>> 24, this[t + 1] = e >>> 16, this[t + 2] = e >>> 8, this[t + 3] = e & 255, t + 4;
	}, s.prototype.writeBigInt64LE = W(function(e, t = 0) {
		return F(this, e, t, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
	}), s.prototype.writeBigInt64BE = W(function(e, t = 0) {
		return oe(this, e, t, -BigInt("0x8000000000000000"), BigInt("0x7fffffffffffffff"));
	});
	function se(e, t, n, r, i, a) {
		if (n + r > e.length || n < 0) throw RangeError("Index out of range");
	}
	function I(e, t, r, i, a) {
		return t = +t, r >>>= 0, a || se(e, t, r, 4, 34028234663852886e22, -34028234663852886e22), n.write(e, t, r, i, 23, 4), r + 4;
	}
	s.prototype.writeFloatLE = function(e, t, n) {
		return I(this, e, t, !0, n);
	}, s.prototype.writeFloatBE = function(e, t, n) {
		return I(this, e, t, !1, n);
	};
	function L(e, t, r, i, a) {
		return t = +t, r >>>= 0, a || se(e, t, r, 8, 17976931348623157e292, -17976931348623157e292), n.write(e, t, r, i, 52, 8), r + 8;
	}
	s.prototype.writeDoubleLE = function(e, t, n) {
		return L(this, e, t, !0, n);
	}, s.prototype.writeDoubleBE = function(e, t, n) {
		return L(this, e, t, !1, n);
	}, s.prototype.copy = function(e, t, n, r) {
		if (!s.isBuffer(e)) throw TypeError("argument should be a Buffer");
		if (n ||= 0, !r && r !== 0 && (r = this.length), t >= e.length && (t = e.length), t ||= 0, r > 0 && r < n && (r = n), r === n || e.length === 0 || this.length === 0) return 0;
		if (t < 0) throw RangeError("targetStart out of bounds");
		if (n < 0 || n >= this.length) throw RangeError("Index out of range");
		if (r < 0) throw RangeError("sourceEnd out of bounds");
		r > this.length && (r = this.length), e.length - t < r - n && (r = e.length - t + n);
		let i = r - n;
		return this === e && typeof Uint8Array.prototype.copyWithin == "function" ? this.copyWithin(t, n, r) : Uint8Array.prototype.set.call(e, this.subarray(n, r), t), i;
	}, s.prototype.fill = function(e, t, n, r) {
		if (typeof e == "string") {
			if (typeof t == "string" ? (r = t, t = 0, n = this.length) : typeof n == "string" && (r = n, n = this.length), r !== void 0 && typeof r != "string") throw TypeError("encoding must be a string");
			if (typeof r == "string" && !s.isEncoding(r)) throw TypeError("Unknown encoding: " + r);
			if (e.length === 1) {
				let t = e.charCodeAt(0);
				(r === "utf8" && t < 128 || r === "latin1") && (e = t);
			}
		} else typeof e == "number" ? e &= 255 : typeof e == "boolean" && (e = Number(e));
		if (t < 0 || this.length < t || this.length < n) throw RangeError("Out of range index");
		if (n <= t) return this;
		t >>>= 0, n = n === void 0 ? this.length : n >>> 0, e ||= 0;
		let i;
		if (typeof e == "number") for (i = t; i < n; ++i) this[i] = e;
		else {
			let a = s.isBuffer(e) ? e : s.from(e, r), o = a.length;
			if (o === 0) throw TypeError("The value \"" + e + "\" is invalid for argument \"value\"");
			for (i = 0; i < n - t; ++i) this[i + t] = a[i % o];
		}
		return this;
	};
	var ce = {};
	function R(e, t, n) {
		ce[e] = class extends n {
			constructor() {
				super(), Object.defineProperty(this, "message", {
					value: t.apply(this, arguments),
					writable: !0,
					configurable: !0
				}), this.name = `${this.name} [${e}]`, this.stack, delete this.name;
			}
			get code() {
				return e;
			}
			set code(e) {
				Object.defineProperty(this, "code", {
					configurable: !0,
					enumerable: !0,
					value: e,
					writable: !0
				});
			}
			toString() {
				return `${this.name} [${e}]: ${this.message}`;
			}
		};
	}
	R("ERR_BUFFER_OUT_OF_BOUNDS", function(e) {
		return e ? `${e} is outside of buffer bounds` : "Attempt to access memory outside buffer bounds";
	}, RangeError), R("ERR_INVALID_ARG_TYPE", function(e, t) {
		return `The "${e}" argument must be of type number. Received type ${typeof t}`;
	}, TypeError), R("ERR_OUT_OF_RANGE", function(e, t, n) {
		let r = `The value of "${e}" is out of range.`, i = n;
		return Number.isInteger(n) && Math.abs(n) > 2 ** 32 ? i = le(String(n)) : typeof n == "bigint" && (i = String(n), (n > BigInt(2) ** BigInt(32) || n < -(BigInt(2) ** BigInt(32))) && (i = le(i)), i += "n"), r += ` It must be ${t}. Received ${i}`, r;
	}, RangeError);
	function le(e) {
		let t = "", n = e.length, r = e[0] === "-" ? 1 : 0;
		for (; n >= r + 4; n -= 3) t = `_${e.slice(n - 3, n)}${t}`;
		return `${e.slice(0, n)}${t}`;
	}
	function ue(e, t, n) {
		B(t, "offset"), (e[t] === void 0 || e[t + n] === void 0) && de(t, e.length - (n + 1));
	}
	function z(e, t, n, r, i, a) {
		if (e > n || e < t) {
			let r = typeof t == "bigint" ? "n" : "", i;
			throw i = a > 3 ? t === 0 || t === BigInt(0) ? `>= 0${r} and < 2${r} ** ${(a + 1) * 8}${r}` : `>= -(2${r} ** ${(a + 1) * 8 - 1}${r}) and < 2 ** ${(a + 1) * 8 - 1}${r}` : `>= ${t}${r} and <= ${n}${r}`, new ce.ERR_OUT_OF_RANGE("value", i, e);
		}
		ue(r, i, a);
	}
	function B(e, t) {
		if (typeof e != "number") throw new ce.ERR_INVALID_ARG_TYPE(t, "number", e);
	}
	function de(e, t, n) {
		throw Math.floor(e) === e ? t < 0 ? new ce.ERR_BUFFER_OUT_OF_BOUNDS() : new ce.ERR_OUT_OF_RANGE(n || "offset", `>= ${n ? 1 : 0} and <= ${t}`, e) : (B(e, n), new ce.ERR_OUT_OF_RANGE(n || "offset", "an integer", e));
	}
	var fe = /[^+/0-9A-Za-z-_]/g;
	function pe(e) {
		if (e = e.split("=")[0], e = e.trim().replace(fe, ""), e.length < 2) return "";
		for (; e.length % 4 != 0;) e += "=";
		return e;
	}
	function me(e, t) {
		t ||= Infinity;
		let n, r = e.length, i = null, a = [];
		for (let o = 0; o < r; ++o) {
			if (n = e.charCodeAt(o), n > 55295 && n < 57344) {
				if (!i) {
					if (n > 56319) {
						(t -= 3) > -1 && a.push(239, 191, 189);
						continue;
					} else if (o + 1 === r) {
						(t -= 3) > -1 && a.push(239, 191, 189);
						continue;
					}
					i = n;
					continue;
				}
				if (n < 56320) {
					(t -= 3) > -1 && a.push(239, 191, 189), i = n;
					continue;
				}
				n = (i - 55296 << 10 | n - 56320) + 65536;
			} else i && (t -= 3) > -1 && a.push(239, 191, 189);
			if (i = null, n < 128) {
				if (--t < 0) break;
				a.push(n);
			} else if (n < 2048) {
				if ((t -= 2) < 0) break;
				a.push(n >> 6 | 192, n & 63 | 128);
			} else if (n < 65536) {
				if ((t -= 3) < 0) break;
				a.push(n >> 12 | 224, n >> 6 & 63 | 128, n & 63 | 128);
			} else if (n < 1114112) {
				if ((t -= 4) < 0) break;
				a.push(n >> 18 | 240, n >> 12 & 63 | 128, n >> 6 & 63 | 128, n & 63 | 128);
			} else throw Error("Invalid code point");
		}
		return a;
	}
	function V(e) {
		let t = [];
		for (let n = 0; n < e.length; ++n) t.push(e.charCodeAt(n) & 255);
		return t;
	}
	function he(e, t) {
		let n, r, i, a = [];
		for (let o = 0; o < e.length && !((t -= 2) < 0); ++o) n = e.charCodeAt(o), r = n >> 8, i = n % 256, a.push(i), a.push(r);
		return a;
	}
	function ge(e) {
		return t.toByteArray(pe(e));
	}
	function H(e, t, n, r) {
		let i;
		for (i = 0; i < r && !(i + n >= t.length || i >= e.length); ++i) t[i + n] = e[i];
		return i;
	}
	function U(e, t) {
		return e instanceof t || e != null && e.constructor != null && e.constructor.name != null && e.constructor.name === t.name;
	}
	function _e(e) {
		return e !== e;
	}
	var ve = (function() {
		let e = "0123456789abcdef", t = Array(256);
		for (let n = 0; n < 16; ++n) {
			let r = n * 16;
			for (let i = 0; i < 16; ++i) t[r + i] = e[n] + e[i];
		}
		return t;
	})();
	function W(e) {
		return typeof BigInt > "u" ? ye : e;
	}
	function ye() {
		throw Error("BigInt not supported");
	}
})))();
function g(e, ...t) {
	return t.reduce((t, n) => {
		let r = y(n);
		for (let t of r) e.push(t);
		return t;
	}, e);
}
function _(...e) {
	return new Uint8Array(g([], ...e));
}
function v(e, t) {
	return h.Buffer.from(y(e)).toString(t);
}
function y(e, t) {
	if (e instanceof Uint8Array) return e;
	if (e instanceof ArrayBuffer) return new Uint8Array(e);
	if (typeof e == "string") {
		if (t !== void 0) return h.Buffer.from(e, t);
		let n = e.startsWith("0x") ? e.slice(2) : e, r = n.length % 2 == 0 ? n : `0${n}`, i = h.Buffer.from(r, "hex");
		if (i.length * 2 !== r.length) throw Error(`Invalid bytes ${e}`);
		return i;
	}
	if (Array.from(e).some((e) => e < 0 || 255 < e)) throw Error(`Invalid bytes ${JSON.stringify(e)}`);
	return new Uint8Array(e);
}
function b(e, t) {
	if (e === t) return !0;
	let n = y(e), r = y(t);
	if (n.length !== r.length) return !1;
	for (let e = 0; e < n.length; e++) if (n[e] !== r[e]) return !1;
	return !0;
}
//#endregion
//#region node_modules/@noble/hashes/esm/crypto.js
var x = typeof globalThis == "object" && "crypto" in globalThis ? globalThis.crypto : void 0;
//#endregion
//#region node_modules/@noble/hashes/esm/utils.js
function S(e) {
	return e instanceof Uint8Array || ArrayBuffer.isView(e) && e.constructor.name === "Uint8Array";
}
function C(e) {
	if (!Number.isSafeInteger(e) || e < 0) throw Error("positive integer expected, got " + e);
}
function w(e, ...t) {
	if (!S(e)) throw Error("Uint8Array expected");
	if (t.length > 0 && !t.includes(e.length)) throw Error("Uint8Array expected of length " + t + ", got length=" + e.length);
}
function T(e) {
	if (typeof e != "function" || typeof e.create != "function") throw Error("Hash should be wrapped by utils.createHasher");
	C(e.outputLen), C(e.blockLen);
}
function E(e, t = !0) {
	if (e.destroyed) throw Error("Hash instance has been destroyed");
	if (t && e.finished) throw Error("Hash#digest() has already been called");
}
function D(e, t) {
	w(e);
	let n = t.outputLen;
	if (e.length < n) throw Error("digestInto() expects output buffer of length at least " + n);
}
function ee(e) {
	return new Uint32Array(e.buffer, e.byteOffset, Math.floor(e.byteLength / 4));
}
function O(...e) {
	for (let t = 0; t < e.length; t++) e[t].fill(0);
}
function k(e) {
	return new DataView(e.buffer, e.byteOffset, e.byteLength);
}
function te(e, t) {
	return e << 32 - t | e >>> t;
}
function A(e, t) {
	return e << t | e >>> 32 - t >>> 0;
}
var j = new Uint8Array(new Uint32Array([287454020]).buffer)[0] === 68;
function ne(e) {
	return e << 24 & 4278190080 | e << 8 & 16711680 | e >>> 8 & 65280 | e >>> 24 & 255;
}
var M = j ? (e) => e : (e) => ne(e);
function N(e) {
	for (let t = 0; t < e.length; t++) e[t] = ne(e[t]);
	return e;
}
var re = j ? (e) => e : N, ie = typeof Uint8Array.from([]).toHex == "function" && typeof Uint8Array.fromHex == "function", P = /* @__PURE__ */ Array.from({ length: 256 }, (e, t) => t.toString(16).padStart(2, "0"));
function ae(e) {
	if (w(e), ie) return e.toHex();
	let t = "";
	for (let n = 0; n < e.length; n++) t += P[e[n]];
	return t;
}
var F = {
	_0: 48,
	_9: 57,
	A: 65,
	F: 70,
	a: 97,
	f: 102
};
function oe(e) {
	if (e >= F._0 && e <= F._9) return e - F._0;
	if (e >= F.A && e <= F.F) return e - (F.A - 10);
	if (e >= F.a && e <= F.f) return e - (F.a - 10);
}
function se(e) {
	if (typeof e != "string") throw Error("hex string expected, got " + typeof e);
	if (ie) return Uint8Array.fromHex(e);
	let t = e.length, n = t / 2;
	if (t % 2) throw Error("hex string expected, got unpadded hex of length " + t);
	let r = new Uint8Array(n);
	for (let t = 0, i = 0; t < n; t++, i += 2) {
		let n = oe(e.charCodeAt(i)), a = oe(e.charCodeAt(i + 1));
		if (n === void 0 || a === void 0) {
			let t = e[i] + e[i + 1];
			throw Error("hex string expected, got non-hex character \"" + t + "\" at index " + i);
		}
		r[t] = n * 16 + a;
	}
	return r;
}
function I(e) {
	if (typeof e != "string") throw Error("string expected");
	return new Uint8Array(new TextEncoder().encode(e));
}
function L(e) {
	return typeof e == "string" && (e = I(e)), w(e), e;
}
function ce(...e) {
	let t = 0;
	for (let n = 0; n < e.length; n++) {
		let r = e[n];
		w(r), t += r.length;
	}
	let n = new Uint8Array(t);
	for (let t = 0, r = 0; t < e.length; t++) {
		let i = e[t];
		n.set(i, r), r += i.length;
	}
	return n;
}
var R = class {};
function le(e) {
	let t = (t) => e().update(L(t)).digest(), n = e();
	return t.outputLen = n.outputLen, t.blockLen = n.blockLen, t.create = () => e(), t;
}
function ue(e) {
	let t = (t, n) => e(n).update(L(t)).digest(), n = e({});
	return t.outputLen = n.outputLen, t.blockLen = n.blockLen, t.create = (t) => e(t), t;
}
function z(e = 32) {
	if (x && typeof x.getRandomValues == "function") return x.getRandomValues(new Uint8Array(e));
	if (x && typeof x.randomBytes == "function") return Uint8Array.from(x.randomBytes(e));
	throw Error("crypto.getRandomValues must be defined");
}
//#endregion
//#region node_modules/@noble/hashes/esm/_blake.js
var B = /* @__PURE__ */ Uint8Array.from([
	0,
	1,
	2,
	3,
	4,
	5,
	6,
	7,
	8,
	9,
	10,
	11,
	12,
	13,
	14,
	15,
	14,
	10,
	4,
	8,
	9,
	15,
	13,
	6,
	1,
	12,
	0,
	2,
	11,
	7,
	5,
	3,
	11,
	8,
	12,
	0,
	5,
	2,
	15,
	13,
	10,
	14,
	3,
	6,
	7,
	1,
	9,
	4,
	7,
	9,
	3,
	1,
	13,
	12,
	11,
	14,
	2,
	6,
	5,
	10,
	4,
	0,
	15,
	8,
	9,
	0,
	5,
	7,
	2,
	4,
	10,
	15,
	14,
	1,
	11,
	12,
	6,
	8,
	3,
	13,
	2,
	12,
	6,
	10,
	0,
	11,
	8,
	3,
	4,
	13,
	7,
	5,
	15,
	14,
	1,
	9,
	12,
	5,
	1,
	15,
	14,
	13,
	4,
	10,
	0,
	7,
	6,
	3,
	9,
	2,
	8,
	11,
	13,
	11,
	7,
	14,
	12,
	1,
	3,
	9,
	5,
	0,
	15,
	4,
	8,
	6,
	2,
	10,
	6,
	15,
	14,
	9,
	11,
	3,
	0,
	8,
	12,
	2,
	13,
	7,
	1,
	4,
	10,
	5,
	10,
	2,
	8,
	4,
	7,
	6,
	1,
	5,
	15,
	11,
	9,
	14,
	3,
	12,
	13,
	0,
	0,
	1,
	2,
	3,
	4,
	5,
	6,
	7,
	8,
	9,
	10,
	11,
	12,
	13,
	14,
	15,
	14,
	10,
	4,
	8,
	9,
	15,
	13,
	6,
	1,
	12,
	0,
	2,
	11,
	7,
	5,
	3,
	11,
	8,
	12,
	0,
	5,
	2,
	15,
	13,
	10,
	14,
	3,
	6,
	7,
	1,
	9,
	4,
	7,
	9,
	3,
	1,
	13,
	12,
	11,
	14,
	2,
	6,
	5,
	10,
	4,
	0,
	15,
	8,
	9,
	0,
	5,
	7,
	2,
	4,
	10,
	15,
	14,
	1,
	11,
	12,
	6,
	8,
	3,
	13,
	2,
	12,
	6,
	10,
	0,
	11,
	8,
	3,
	4,
	13,
	7,
	5,
	15,
	14,
	1,
	9
]);
//#endregion
//#region node_modules/@noble/hashes/esm/_md.js
function de(e, t, n, r) {
	if (typeof e.setBigUint64 == "function") return e.setBigUint64(t, n, r);
	let i = BigInt(32), a = BigInt(4294967295), o = Number(n >> i & a), s = Number(n & a), c = r ? 4 : 0, l = r ? 0 : 4;
	e.setUint32(t + c, o, r), e.setUint32(t + l, s, r);
}
function fe(e, t, n) {
	return e & t ^ ~e & n;
}
function pe(e, t, n) {
	return e & t ^ e & n ^ t & n;
}
var me = class extends R {
	constructor(e, t, n, r) {
		super(), this.finished = !1, this.length = 0, this.pos = 0, this.destroyed = !1, this.blockLen = e, this.outputLen = t, this.padOffset = n, this.isLE = r, this.buffer = new Uint8Array(e), this.view = k(this.buffer);
	}
	update(e) {
		E(this), e = L(e), w(e);
		let { view: t, buffer: n, blockLen: r } = this, i = e.length;
		for (let a = 0; a < i;) {
			let o = Math.min(r - this.pos, i - a);
			if (o === r) {
				let t = k(e);
				for (; r <= i - a; a += r) this.process(t, a);
				continue;
			}
			n.set(e.subarray(a, a + o), this.pos), this.pos += o, a += o, this.pos === r && (this.process(t, 0), this.pos = 0);
		}
		return this.length += e.length, this.roundClean(), this;
	}
	digestInto(e) {
		E(this), D(e, this), this.finished = !0;
		let { buffer: t, view: n, blockLen: r, isLE: i } = this, { pos: a } = this;
		t[a++] = 128, O(this.buffer.subarray(a)), this.padOffset > r - a && (this.process(n, 0), a = 0);
		for (let e = a; e < r; e++) t[e] = 0;
		de(n, r - 8, BigInt(this.length * 8), i), this.process(n, 0);
		let o = k(e), s = this.outputLen;
		if (s % 4) throw Error("_sha2: outputLen should be aligned to 32bit");
		let c = s / 4, l = this.get();
		if (c > l.length) throw Error("_sha2: outputLen bigger than state");
		for (let e = 0; e < c; e++) o.setUint32(4 * e, l[e], i);
	}
	digest() {
		let { buffer: e, outputLen: t } = this;
		this.digestInto(e);
		let n = e.slice(0, t);
		return this.destroy(), n;
	}
	_cloneInto(e) {
		e ||= new this.constructor(), e.set(...this.get());
		let { blockLen: t, buffer: n, length: r, finished: i, destroyed: a, pos: o } = this;
		return e.destroyed = a, e.finished = i, e.length = r, e.pos = o, r % t && e.buffer.set(n), e;
	}
	clone() {
		return this._cloneInto();
	}
}, V = /* @__PURE__ */ Uint32Array.from([
	1779033703,
	3144134277,
	1013904242,
	2773480762,
	1359893119,
	2600822924,
	528734635,
	1541459225
]), he = /* @__PURE__ */ BigInt(2 ** 32 - 1), ge = /* @__PURE__ */ BigInt(32);
function H(e, t = !1) {
	return t ? {
		h: Number(e & he),
		l: Number(e >> ge & he)
	} : {
		h: Number(e >> ge & he) | 0,
		l: Number(e & he) | 0
	};
}
function U(e, t = !1) {
	let n = e.length, r = new Uint32Array(n), i = new Uint32Array(n);
	for (let a = 0; a < n; a++) {
		let { h: n, l: o } = H(e[a], t);
		[r[a], i[a]] = [n, o];
	}
	return [r, i];
}
var _e = (e, t, n) => e >>> n | t << 32 - n, ve = (e, t, n) => e << 32 - n | t >>> n, W = (e, t, n) => e << 64 - n | t >>> n - 32, ye = (e, t, n) => e >>> n - 32 | t << 64 - n, be = (e, t) => t, xe = (e, t) => e;
function Se(e, t, n, r) {
	let i = (t >>> 0) + (r >>> 0);
	return {
		h: e + n + (i / 2 ** 32 | 0) | 0,
		l: i | 0
	};
}
var Ce = (e, t, n) => (e >>> 0) + (t >>> 0) + (n >>> 0), we = (e, t, n, r) => t + n + r + (e / 2 ** 32 | 0) | 0, Te = /* @__PURE__ */ Uint32Array.from([
	4089235720,
	1779033703,
	2227873595,
	3144134277,
	4271175723,
	1013904242,
	1595750129,
	2773480762,
	2917565137,
	1359893119,
	725511199,
	2600822924,
	4215389547,
	528734635,
	327033209,
	1541459225
]), G = /* @__PURE__ */ new Uint32Array(32);
function Ee(e, t, n, r, i, a) {
	let o = i[a], s = i[a + 1], c = G[2 * e], l = G[2 * e + 1], u = G[2 * t], d = G[2 * t + 1], f = G[2 * n], p = G[2 * n + 1], m = G[2 * r], h = G[2 * r + 1], g = Ce(c, u, o);
	l = we(g, l, d, s), c = g | 0, {Dh: h, Dl: m} = {
		Dh: h ^ l,
		Dl: m ^ c
	}, {Dh: h, Dl: m} = {
		Dh: be(h, m),
		Dl: xe(h, m)
	}, {h: p, l: f} = Se(p, f, h, m), {Bh: d, Bl: u} = {
		Bh: d ^ p,
		Bl: u ^ f
	}, {Bh: d, Bl: u} = {
		Bh: _e(d, u, 24),
		Bl: ve(d, u, 24)
	}, G[2 * e] = c, G[2 * e + 1] = l, G[2 * t] = u, G[2 * t + 1] = d, G[2 * n] = f, G[2 * n + 1] = p, G[2 * r] = m, G[2 * r + 1] = h;
}
function De(e, t, n, r, i, a) {
	let o = i[a], s = i[a + 1], c = G[2 * e], l = G[2 * e + 1], u = G[2 * t], d = G[2 * t + 1], f = G[2 * n], p = G[2 * n + 1], m = G[2 * r], h = G[2 * r + 1], g = Ce(c, u, o);
	l = we(g, l, d, s), c = g | 0, {Dh: h, Dl: m} = {
		Dh: h ^ l,
		Dl: m ^ c
	}, {Dh: h, Dl: m} = {
		Dh: _e(h, m, 16),
		Dl: ve(h, m, 16)
	}, {h: p, l: f} = Se(p, f, h, m), {Bh: d, Bl: u} = {
		Bh: d ^ p,
		Bl: u ^ f
	}, {Bh: d, Bl: u} = {
		Bh: W(d, u, 63),
		Bl: ye(d, u, 63)
	}, G[2 * e] = c, G[2 * e + 1] = l, G[2 * t] = u, G[2 * t + 1] = d, G[2 * n] = f, G[2 * n + 1] = p, G[2 * r] = m, G[2 * r + 1] = h;
}
function Oe(e, t = {}, n, r, i) {
	if (C(n), e < 0 || e > n) throw Error("outputLen bigger than keyLen");
	let { key: a, salt: o, personalization: s } = t;
	if (a !== void 0 && (a.length < 1 || a.length > n)) throw Error("key length must be undefined or 1.." + n);
	if (o !== void 0 && o.length !== r) throw Error("salt must be undefined or " + r);
	if (s !== void 0 && s.length !== i) throw Error("personalization must be undefined or " + i);
}
var ke = class extends R {
	constructor(e, t) {
		super(), this.finished = !1, this.destroyed = !1, this.length = 0, this.pos = 0, C(e), C(t), this.blockLen = e, this.outputLen = t, this.buffer = new Uint8Array(e), this.buffer32 = ee(this.buffer);
	}
	update(e) {
		E(this), e = L(e), w(e);
		let { blockLen: t, buffer: n, buffer32: r } = this, i = e.length, a = e.byteOffset, o = e.buffer;
		for (let s = 0; s < i;) {
			this.pos === t && (re(r), this.compress(r, 0, !1), re(r), this.pos = 0);
			let c = Math.min(t - this.pos, i - s), l = a + s;
			if (c === t && !(l % 4) && s + c < i) {
				let e = new Uint32Array(o, l, Math.floor((i - s) / 4));
				re(e);
				for (let n = 0; s + t < i; n += r.length, s += t) this.length += t, this.compress(e, n, !1);
				re(e);
				continue;
			}
			n.set(e.subarray(s, s + c), this.pos), this.pos += c, this.length += c, s += c;
		}
		return this;
	}
	digestInto(e) {
		E(this), D(e, this);
		let { pos: t, buffer32: n } = this;
		this.finished = !0, O(this.buffer.subarray(t)), re(n), this.compress(n, 0, !0), re(n);
		let r = ee(e);
		this.get().forEach((e, t) => r[t] = M(e));
	}
	digest() {
		let { buffer: e, outputLen: t } = this;
		this.digestInto(e);
		let n = e.slice(0, t);
		return this.destroy(), n;
	}
	_cloneInto(e) {
		let { buffer: t, length: n, finished: r, destroyed: i, outputLen: a, pos: o } = this;
		return e ||= new this.constructor({ dkLen: a }), e.set(...this.get()), e.buffer.set(t), e.destroyed = i, e.finished = r, e.length = n, e.pos = o, e.outputLen = a, e;
	}
	clone() {
		return this._cloneInto();
	}
}, Ae = class extends ke {
	constructor(e = {}) {
		let t = e.dkLen === void 0 ? 64 : e.dkLen;
		super(128, t), this.v0l = Te[0] | 0, this.v0h = Te[1] | 0, this.v1l = Te[2] | 0, this.v1h = Te[3] | 0, this.v2l = Te[4] | 0, this.v2h = Te[5] | 0, this.v3l = Te[6] | 0, this.v3h = Te[7] | 0, this.v4l = Te[8] | 0, this.v4h = Te[9] | 0, this.v5l = Te[10] | 0, this.v5h = Te[11] | 0, this.v6l = Te[12] | 0, this.v6h = Te[13] | 0, this.v7l = Te[14] | 0, this.v7h = Te[15] | 0, Oe(t, e, 64, 16, 16);
		let { key: n, personalization: r, salt: i } = e, a = 0;
		if (n !== void 0 && (n = L(n), a = n.length), this.v0l ^= this.outputLen | a << 8 | 16842752, i !== void 0) {
			i = L(i);
			let e = ee(i);
			this.v4l ^= M(e[0]), this.v4h ^= M(e[1]), this.v5l ^= M(e[2]), this.v5h ^= M(e[3]);
		}
		if (r !== void 0) {
			r = L(r);
			let e = ee(r);
			this.v6l ^= M(e[0]), this.v6h ^= M(e[1]), this.v7l ^= M(e[2]), this.v7h ^= M(e[3]);
		}
		if (n !== void 0) {
			let e = new Uint8Array(this.blockLen);
			e.set(n), this.update(e);
		}
	}
	get() {
		let { v0l: e, v0h: t, v1l: n, v1h: r, v2l: i, v2h: a, v3l: o, v3h: s, v4l: c, v4h: l, v5l: u, v5h: d, v6l: f, v6h: p, v7l: m, v7h: h } = this;
		return [
			e,
			t,
			n,
			r,
			i,
			a,
			o,
			s,
			c,
			l,
			u,
			d,
			f,
			p,
			m,
			h
		];
	}
	set(e, t, n, r, i, a, o, s, c, l, u, d, f, p, m, h) {
		this.v0l = e | 0, this.v0h = t | 0, this.v1l = n | 0, this.v1h = r | 0, this.v2l = i | 0, this.v2h = a | 0, this.v3l = o | 0, this.v3h = s | 0, this.v4l = c | 0, this.v4h = l | 0, this.v5l = u | 0, this.v5h = d | 0, this.v6l = f | 0, this.v6h = p | 0, this.v7l = m | 0, this.v7h = h | 0;
	}
	compress(e, t, n) {
		this.get().forEach((e, t) => G[t] = e), G.set(Te, 16);
		let { h: r, l: i } = H(BigInt(this.length));
		G[24] = Te[8] ^ i, G[25] = Te[9] ^ r, n && (G[28] = ~G[28], G[29] = ~G[29]);
		let a = 0, o = B;
		for (let n = 0; n < 12; n++) Ee(0, 4, 8, 12, e, t + 2 * o[a++]), De(0, 4, 8, 12, e, t + 2 * o[a++]), Ee(1, 5, 9, 13, e, t + 2 * o[a++]), De(1, 5, 9, 13, e, t + 2 * o[a++]), Ee(2, 6, 10, 14, e, t + 2 * o[a++]), De(2, 6, 10, 14, e, t + 2 * o[a++]), Ee(3, 7, 11, 15, e, t + 2 * o[a++]), De(3, 7, 11, 15, e, t + 2 * o[a++]), Ee(0, 5, 10, 15, e, t + 2 * o[a++]), De(0, 5, 10, 15, e, t + 2 * o[a++]), Ee(1, 6, 11, 12, e, t + 2 * o[a++]), De(1, 6, 11, 12, e, t + 2 * o[a++]), Ee(2, 7, 8, 13, e, t + 2 * o[a++]), De(2, 7, 8, 13, e, t + 2 * o[a++]), Ee(3, 4, 9, 14, e, t + 2 * o[a++]), De(3, 4, 9, 14, e, t + 2 * o[a++]);
		this.v0l ^= G[0] ^ G[16], this.v0h ^= G[1] ^ G[17], this.v1l ^= G[2] ^ G[18], this.v1h ^= G[3] ^ G[19], this.v2l ^= G[4] ^ G[20], this.v2h ^= G[5] ^ G[21], this.v3l ^= G[6] ^ G[22], this.v3h ^= G[7] ^ G[23], this.v4l ^= G[8] ^ G[24], this.v4h ^= G[9] ^ G[25], this.v5l ^= G[10] ^ G[26], this.v5h ^= G[11] ^ G[27], this.v6l ^= G[12] ^ G[28], this.v6h ^= G[13] ^ G[29], this.v7l ^= G[14] ^ G[30], this.v7h ^= G[15] ^ G[31], O(G);
	}
	destroy() {
		this.destroyed = !0, O(this.buffer32), this.set(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
	}
}, je = /* @__PURE__ */ ue((e) => new Ae(e));
//#endregion
//#region node_modules/@ckb-ccc/core/dist/hex/index.js
function K(e) {
	return `0x${v(y(e), "hex")}`;
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/hasher/advanced.js
var Me = "ckb-default-hash", Ne = class {
	constructor(e = 32, t = Me) {
		this.hasher = je.create({
			personalization: t,
			dkLen: e
		});
	}
	update(e) {
		return this.hasher.update(y(e)), this;
	}
	digest() {
		return K(this.hasher.digest());
	}
};
function Pe(...e) {
	let t = new Ne();
	return e.forEach((e) => t.update(e)), t.digest();
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/num/index.js
function Fe(e, ...t) {
	let n = q(e);
	return t.forEach((e) => {
		let t = q(e);
		t < n && (n = t);
	}), n;
}
function Ie(e, ...t) {
	let n = q(e);
	return t.forEach((e) => {
		let t = q(e);
		t > n && (n = t);
	}), n;
}
function q(e) {
	if (typeof e == "bigint") return e;
	if (e === "0x") return BigInt(0);
	if (typeof e == "string" || typeof e == "number") return BigInt(e);
	let t = K(e);
	return BigInt(t);
}
function Le(e) {
	return `0x${q(e).toString(16)}`;
}
function Re(e, t) {
	return ze(e, t);
}
function ze(e, t) {
	return Be(e, t).reverse();
}
function Be(e, t) {
	let n = q(e);
	if (n < q(0)) {
		if (t == null) throw Error("negative number can not be serialized without knowing bytes length");
		if (n = (q(1) << q(8) * q(t)) + n, n < 0) throw Error("negative number underflow");
	}
	let r = y(n.toString(16));
	if (t == null) return r;
	if (r.length > t) throw Error("number overflow");
	return _("00".repeat(t - r.length), r);
}
function Ve(e) {
	return He(e);
}
function He(e) {
	return Ue(y(e).map((e) => e).reverse());
}
function Ue(e) {
	return q(y(e));
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/client/clientTypes.advanced.js
var We = q(1e7), Ge = q(1e3);
function Ke([e, t]) {
	return [q(e), q(t)];
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/utils/index.js
function J(e, t) {
	if (t != null) return e(t);
}
async function qe(e, t, n) {
	if (n === void 0) {
		if (e.length === 0) throw TypeError("Reduce of empty array with no initial value");
		n = e[0], e = e.slice(1);
	}
	return e.reduce((e, n, r, i) => e.then((e) => Promise.resolve(t(e, n, r, i)).then((t) => t ?? e)), Promise.resolve(n));
}
function Je(e) {
	return new Promise((t) => setTimeout(t, Number(q(e))));
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/client/clientTypes.js
var Ye = class e {
	constructor(e, t) {
		this.cellDep = e, this.type = t;
	}
	static from(t) {
		return t instanceof e ? t : new e(rr.from(t.cellDep), J(X.from, t.type));
	}
}, Xe = class e {
	constructor(e, t, n) {
		this.codeHash = e, this.hashType = t, this.cellDeps = n;
	}
	static from(t) {
		return t instanceof e ? t : new e(K(t.codeHash), Dn(t.hashType), t.cellDeps.map((e) => Ye.from(e)));
	}
}, Ze = class e {
	constructor(e, t, n, r, i, a, o) {
		this.transaction = e, this.status = t, this.cycles = n, this.blockHash = r, this.blockNumber = i, this.txIndex = a, this.reason = o;
	}
	static from(t) {
		return t instanceof e ? t : new e(cr.from(t.transaction), t.status, J(q, t.cycles), J(K, t.blockHash), J(q, t.blockNumber), J(q, t.txIndex), t.reason);
	}
	clone() {
		return new e(this.transaction.clone(), this.status, this.cycles, this.blockHash, this.blockNumber, this.txIndex, this.reason);
	}
}, Qe = class e {
	constructor(e, t, n, r, i, a, o) {
		this.script = e, this.scriptLenRange = t, this.outputData = n, this.outputDataSearchMode = r, this.outputDataLenRange = i, this.outputCapacityRange = a, this.blockRange = o;
	}
	static from(t) {
		return t instanceof e ? t : new e(J(X.from, t.script), J(Ke, t.scriptLenRange), J(K, t.outputData), t.outputDataSearchMode ?? void 0, J(Ke, t.outputDataLenRange), J(Ke, t.outputCapacityRange), J(Ke, t.blockRange));
	}
}, $e = class e {
	constructor(e, t, n, r, i) {
		this.script = e, this.scriptType = t, this.scriptSearchMode = n, this.filter = r, this.withData = i;
	}
	static from(t) {
		return t instanceof e ? t : new e(X.from(t.script), t.scriptType, t.scriptSearchMode, J(Qe.from, t.filter), t.withData ?? void 0);
	}
}, et = class e {
	constructor(e, t, n, r, i) {
		this.script = e, this.scriptType = t, this.scriptSearchMode = n, this.filter = r, this.groupByTransaction = i;
	}
	static from(t) {
		return t instanceof e ? t : new e(X.from(t.script), t.scriptType, t.scriptSearchMode, J(Qe.from, t.filter), t.groupByTransaction ?? void 0);
	}
}, tt = class e {
	constructor(e, t, n, r, i, a, o, s, c, l, u, d) {
		this.compactTarget = e, this.dao = t, this.epoch = n, this.extraHash = r, this.hash = i, this.nonce = a, this.number = o, this.parentHash = s, this.proposalsHash = c, this.timestamp = l, this.transactionsRoot = u, this.version = d;
	}
	static from(t) {
		return t instanceof e ? t : new e(q(t.compactTarget), {
			c: q(t.dao.c),
			ar: q(t.dao.ar),
			s: q(t.dao.s),
			u: q(t.dao.u)
		}, Qn(t.epoch), K(t.extraHash), K(t.hash), q(t.nonce), q(t.number), K(t.parentHash), K(t.proposalsHash), q(t.timestamp), K(t.transactionsRoot), q(t.version));
	}
}, nt = class e {
	constructor(e, t) {
		this.header = e, this.proposals = t;
	}
	static from(t) {
		return t instanceof e ? t : new e(tt.from(t.header), t.proposals.map(K));
	}
}, rt = class e {
	constructor(e, t, n, r) {
		this.header = e, this.proposals = t, this.transactions = n, this.uncles = r;
	}
	static from(t) {
		return t instanceof e ? t : new e(tt.from(t.header), t.proposals.map(K), t.transactions.map(cr.from), t.uncles.map(nt.from));
	}
}, it = class extends Error {
	constructor(e) {
		super(`Client request error ${e.message}`), this.code = e.code, this.data = e.data;
	}
}, at = class extends it {
	constructor(e, t) {
		super(e), this.outPoint = qn.from(t);
	}
}, ot = class extends it {
	constructor(e, t, n, r, i, a) {
		super(e), this.source = t, this.errorCode = r, this.scriptHashType = i, this.sourceIndex = q(n), this.scriptCodeHash = K(a);
	}
}, st = class extends it {
	constructor(e, t) {
		super(e), this.txHash = K(t);
	}
}, ct = class extends it {
	constructor(e, t, n) {
		super(e), this.currentFee = q(t), this.leastFee = q(n);
	}
}, lt = class extends it {
	constructor(e) {
		let t = q(e).toString();
		super({
			message: `Wait transaction timeout ${t}ms`,
			data: JSON.stringify({ timeout: t })
		});
	}
}, ut = class extends it {
	constructor(e, t) {
		let n = q(e).toString(), r = q(t).toString();
		super({
			message: `Max fee rate exceeded limit ${n}, actual ${r}. Developer might forgot to complete transaction fee before sending. See https://api.ckbccc.com/classes/_ckb_ccc_core.index.ccc.Transaction.html#completeFeeBy.`,
			data: JSON.stringify({
				limit: n,
				actual: r
			})
		});
	}
}, dt = q(1e3 * 10 * 50);
function ft(e, t, n) {
	if (!t) return !0;
	let r = K(e), i = K(t);
	return !(n === "exact" && r !== i || n === "prefix" && !r.startsWith(i) || n === "partial" && r.search(i) === -1);
}
function pt(e, t, n) {
	if (!t) return !0;
	if (!e) return !1;
	let r = X.from(e), i = X.from(t);
	return r.codeHash !== i.codeHash || r.hashType !== i.hashType ? !1 : ft(r.args, i?.args, n);
}
function mt(e, t) {
	if (!t) return !0;
	let n = q(e), [r, i] = Ke(t);
	return r <= n && n < i;
}
function ht(e, t) {
	return t ? mt(e ? y(X.from(e).args).length + 33 : 0, t) : !0;
}
function gt(e, t) {
	let n = $e.from(e), r = Zn.from(t);
	return !(n.scriptType === "lock" && (!pt(r.cellOutput.lock, n.script, n.scriptSearchMode) || !pt(r.cellOutput.type, n.filter?.script, "prefix") || !ht(r.cellOutput.type, n.filter?.scriptLenRange)) || n.scriptType === "type" && (!pt(r.cellOutput.type, n.script, n.scriptSearchMode) || !pt(r.cellOutput.lock, n.filter?.script, "prefix") || !ht(r.cellOutput.lock, n.filter?.scriptLenRange)) || !ft(r.outputData, n.filter?.outputData, n.filter?.outputDataSearchMode ?? "prefix") || !mt(y(r.outputData).length, n.filter?.outputDataLenRange) || !mt(r.cellOutput.capacity, n.filter?.outputCapacityRange));
}
var _t = class extends Map {
	constructor(e) {
		if (super(), this.capacity = e, this.lru = /* @__PURE__ */ new Set(), !Number.isInteger(e) || e < 1) throw Error("Capacity must be a positive integer");
	}
	get(e) {
		if (super.has(e)) return this.lru.delete(e), this.lru.add(e), super.get(e);
	}
	set(e, t) {
		if (super.set(e, t), this.lru.delete(e), this.lru.add(e), this.lru.size > this.capacity) {
			let e = this.lru.keys().next().value;
			this.delete(e);
		}
		return this;
	}
	delete(e) {
		return super.delete(e) ? (this.lru.delete(e), !0) : !1;
	}
	clear() {
		super.clear(), this.lru.clear();
	}
}, vt = class {
	async markUsable(...e) {
		return await this.recordCells(...e), this.markUsableNoCache(...e);
	}
	async markTransactions(...e) {
		await Promise.all([this.recordTransactionResponses(e.flat().map((e) => ({
			transaction: e,
			status: "sent"
		}))), ...e.flat().map((e) => {
			let t = cr.from(e), n = t.hash();
			return Promise.all([...t.inputs.map((e) => this.markUnusable(e.previousOutput)), ...t.outputs.map((e, r) => this.markUsable({
				cellOutput: e,
				outputData: t.outputsData[r],
				outPoint: {
					txHash: n,
					index: r
				}
			}))]);
		})]);
	}
	async recordCells(...e) {}
	async getCell(e) {}
	async recordTransactionResponses(...e) {}
	async getTransactionResponse(e) {}
	async recordTransactions(...e) {
		return this.recordTransactionResponses(e.flat().map((e) => ({
			transaction: e,
			status: "unknown"
		})));
	}
	async getTransaction(e) {
		return (await this.getTransactionResponse(e))?.transaction;
	}
	async recordHeaders(...e) {}
	async getHeaderByHash(e) {}
	async getHeaderByNumber(e) {}
	async recordBlocks(...e) {}
	async getBlockByHash(e) {}
	async getBlockByNumber(e) {}
	hasHeaderConfirmed(e) {
		return q(Date.now()) - e.timestamp >= dt;
	}
}, yt = class extends vt {
	constructor(e = 512, t = 256, n = 128, r = dt) {
		super(), this.maxCells = e, this.maxTxs = t, this.maxBlocks = n, this.cells = new _t(this.maxCells), this.knownTransactions = new _t(this.maxTxs), this.knownBlockHashes = new _t(this.maxBlocks), this.knownBlocks = new _t(this.maxBlocks), this.confirmedBlockTime = q(r);
	}
	async markUsableNoCache(...e) {
		e.flat().forEach((e) => {
			let t = Zn.from(e).clone(), n = K(t.outPoint.toBytes());
			this.cells.set(n, [!0, t]);
		});
	}
	async markUnusable(...e) {
		e.flat().forEach((e) => {
			let t = qn.from(e), n = K(t.toBytes()), r = this.cells.get(n);
			if (r) {
				r[0] = !1;
				return;
			}
			this.cells.set(n, [!1, { outPoint: t }]);
		});
	}
	async clear() {
		this.cells.clear(), this.knownTransactions.clear();
	}
	async *findCells(e) {
		for (let [t, [n, r]] of this.cells.entries()) n && gt(e, r) && (this.cells.get(t), yield r.clone());
	}
	async isUnusable(e) {
		let t = qn.from(e);
		return !(this.cells.get(K(t.toBytes()))?.[0] ?? !0);
	}
	async recordCells(...e) {
		e.flat().map((e) => {
			let t = Zn.from(e), n = K(t.outPoint.toBytes());
			this.cells.get(n) || this.cells.set(n, [void 0, t]);
		});
	}
	async getCell(e) {
		let t = qn.from(e), n = this.cells.get(K(t.toBytes()))?.[1];
		if (n && n.cellOutput && n.outputData) return Zn.from(n.clone());
	}
	async recordTransactionResponses(...e) {
		e.flat().map((e) => {
			let t = Ze.from(e);
			this.knownTransactions.set(t.transaction.hash(), t);
		});
	}
	async getTransactionResponse(e) {
		let t = K(e);
		return this.knownTransactions.get(t)?.clone();
	}
	async recordHeaders(...e) {
		e.flat().map((e) => {
			let t = tt.from(e);
			this.knownBlockHashes.set(t.number, t.hash), !this.knownBlocks.get(t.hash) && this.knownBlocks.set(t.hash, { header: t });
		});
	}
	async getHeaderByHash(e) {
		let t = K(e), n = this.knownBlocks.get(t);
		return n && this.knownBlockHashes.get(n.header.number), n?.header;
	}
	async getHeaderByNumber(e) {
		let t = q(e), n = this.knownBlockHashes.get(t);
		if (n) return this.getHeaderByHash(n);
	}
	async recordBlocks(...e) {
		e.flat().map((e) => {
			let t = rt.from(e);
			this.knownBlockHashes.set(t.header.number, t.header.hash), this.knownBlocks.set(t.header.hash, t);
		});
	}
	async getBlockByHash(e) {
		let t = K(e), n = this.knownBlocks.get(t);
		if (n && (this.knownBlockHashes.get(n.header.number), "transactions" in n)) return n;
	}
	async getBlockByNumber(e) {
		let t = q(e), n = this.knownBlockHashes.get(t);
		if (n) return this.getBlockByHash(n);
	}
	hasHeaderConfirmed(e) {
		return q(Date.now()) - e.timestamp >= this.confirmedBlockTime;
	}
};
//#endregion
//#region node_modules/@ckb-ccc/core/dist/fixedPoint/index.js
function bt(e, t = 8) {
	let n = xt(e).toString();
	if (t === 0) return n;
	let r = n.length <= t ? "0" : n.slice(0, -t), i = n.slice(-t).padStart(t, "0").replace(/0*$/, "");
	return i === "" ? r : `${r}.${i}`;
}
function xt(e, t = 8) {
	if (typeof e == "bigint") return e;
	let [n, r] = (typeof e == "number" ? e.toFixed(t) : e.toString()).split("."), i = BigInt(n.padEnd(n.length + t, "0"));
	return r === void 0 ? i : i + BigInt(r.slice(0, t).padEnd(t, "0"));
}
var St = 0n;
xt("1");
//#endregion
//#region node_modules/@ckb-ccc/core/dist/client/client.js
var Ct = class {
	constructor(e) {
		this.cache = e?.cache ?? new yt();
	}
	async getFeeRate(e, t) {
		let n = Ie((await this.getFeeRateStatistics(e)).median, Ge), r = q(t?.maxFeeRate ?? We);
		return r === 0n ? n : Fe(n, r);
	}
	async getBlockByNumber(e, t, n) {
		let r = await this.cache.getBlockByNumber(e);
		if (r) return r;
		let i = await this.getBlockByNumberNoCache(e, t, n);
		return i && this.cache.hasHeaderConfirmed(i.header) && await this.cache.recordBlocks(i), i;
	}
	async getBlockByHash(e, t, n) {
		let r = await this.cache.getBlockByHash(e);
		if (r) return r;
		let i = await this.getBlockByHashNoCache(e, t, n);
		return i && this.cache.hasHeaderConfirmed(i.header) && await this.cache.recordBlocks(i), i;
	}
	async getHeaderByNumber(e, t) {
		let n = await this.cache.getHeaderByNumber(e);
		if (n) return n;
		let r = await this.getHeaderByNumberNoCache(e, t);
		return r && this.cache.hasHeaderConfirmed(r) && await this.cache.recordHeaders(r), r;
	}
	async getHeaderByHash(e, t) {
		let n = await this.cache.getHeaderByHash(e);
		if (n) return n;
		let r = await this.getHeaderByHashNoCache(e, t);
		return r && this.cache.hasHeaderConfirmed(r) && await this.cache.recordHeaders(r), r;
	}
	async getCell(e) {
		let t = qn.from(e), n = await this.cache.getCell(t);
		if (n) return n;
		let r = await this.getTransaction(t.txHash);
		if (!r) return;
		let i = r.transaction.getOutput(t.index);
		if (!i) return;
		let a = Zn.from({
			...i,
			outPoint: t
		});
		return await this.cache.recordCells(a), a;
	}
	async getCellWithHeader(e) {
		let t = qn.from(e), n = await this.getTransactionWithHeader(t.txHash);
		if (!n) return;
		let { transaction: r, header: i } = n, a = r.transaction.getOutput(t.index);
		if (!a) return;
		let o = Zn.from({
			...a,
			outPoint: t
		});
		return await this.cache.recordCells(o), {
			cell: o,
			header: i
		};
	}
	async getCellLive(e, t, n) {
		let r = await this.getCellLiveNoCache(e, t, n);
		return t && r && await this.cache.recordCells(r), r;
	}
	async findCellsPaged(e, t, n, r) {
		let i = await this.findCellsPagedNoCache(e, t, n, r);
		return await this.cache.recordCells(i.cells), i;
	}
	async *findCellsOnChain(e, t, n = 10) {
		let r;
		for (;;) {
			let { cells: i, lastCursor: a } = await this.findCellsPaged(e, t, n, r);
			for (let e of i) yield e;
			if (i.length === 0 || i.length < n) return;
			r = a;
		}
	}
	async *findCells(e, t, n = 10) {
		let r = $e.from(e), i = [];
		for await (let e of this.cache.findCells(r)) i.push(e.outPoint), yield e;
		for await (let e of this.findCellsOnChain(r, t, n)) await this.cache.isUnusable(e.outPoint) || i.some((t) => t.eq(e.outPoint)) || (yield e);
	}
	findCellsByLock(e, t, n = !0, r, i = 10) {
		return this.findCells({
			script: e,
			scriptType: "lock",
			scriptSearchMode: "exact",
			filter: { script: t },
			withData: n
		}, r, i);
	}
	findCellsByType(e, t = !0, n, r = 10) {
		return this.findCells({
			script: e,
			scriptType: "type",
			scriptSearchMode: "exact",
			withData: t
		}, n, r);
	}
	async findSingletonCellByType(e, t = !1) {
		for await (let n of this.findCellsByType(e, t, void 0, 1)) return n;
	}
	async getCellDeps(...e) {
		return Promise.all(e.flat().map(async (e) => {
			let { cellDep: t, type: n } = Ye.from(e);
			if (n === void 0) return t;
			let r = await this.findSingletonCellByType(n);
			return r ? rr.from({
				outPoint: r.outPoint,
				depType: t.depType
			}) : t;
		}));
	}
	async *findTransactions(e, t, n = 10) {
		let r;
		for (;;) {
			let { transactions: i, lastCursor: a } = await this.findTransactionsPaged(e, t, n, r);
			for (let e of i) yield e;
			if (i.length === 0 || i.length < n) return;
			r = a;
		}
	}
	findTransactionsByLock(e, t, n, r, i = 10) {
		return this.findTransactions({
			script: e,
			scriptType: "lock",
			scriptSearchMode: "exact",
			filter: { script: t },
			groupByTransaction: n
		}, r, i);
	}
	findTransactionsByType(e, t, n, r = 10) {
		return this.findTransactions({
			script: e,
			scriptType: "type",
			scriptSearchMode: "exact",
			groupByTransaction: t
		}, n, r);
	}
	async getBalanceSingle(e) {
		return this.getCellsCapacity({
			script: e,
			scriptType: "lock",
			scriptSearchMode: "exact",
			filter: {
				scriptLenRange: [0, 1],
				outputDataLenRange: [0, 1]
			}
		});
	}
	async getBalance(e) {
		return qe(e, async (e, t) => e + await this.getBalanceSingle(t), St);
	}
	async sendTransaction(e, t, n) {
		let r = cr.from(e), i = q(n?.maxFeeRate ?? We), a = await r.getFeeRate(this);
		if (i > 0n && a > i) throw new ut(i, a);
		let o = await this.sendTransactionNoCache(r, t);
		return await this.cache.markTransactions(r), o;
	}
	async getTransaction(e) {
		let t = K(e), n = await this.getTransactionNoCache(t);
		return n ? (await this.cache.recordTransactionResponses(n), n) : this.cache.getTransactionResponse(t);
	}
	async getTransactionWithHeader(e) {
		let t = K(e), n = await this.cache.getTransactionResponse(t);
		if (n?.blockHash) {
			let e = await this.getHeaderByHash(n.blockHash);
			if (e && this.cache.hasHeaderConfirmed(e)) return {
				transaction: n,
				header: e
			};
		}
		let r = await this.getTransactionNoCache(t);
		if (r) return await this.cache.recordTransactionResponses(r), {
			transaction: r,
			header: r.blockHash ? await this.getHeaderByHash(r.blockHash) : void 0
		};
	}
	async waitTransaction(e, t = 0, n = 6e4, r = 2e3) {
		let i = Date.now(), a, o = async () => {
			let t = await this.getTransaction(e);
			if (!(!t || t.blockNumber == null || [
				"sent",
				"pending",
				"proposed"
			].includes(t.status))) return a = t, t;
		};
		for (;;) {
			if (!a) {
				if (await o()) continue;
			} else if (t === 0) return a;
			else if ((await this.getTipHeader()).number - a.blockNumber >= t) return a;
			if (Date.now() - i + r >= n) throw new lt(n);
			await Je(r);
		}
	}
}, wt = null;
typeof WebSocket < "u" ? wt = WebSocket : typeof MozWebSocket < "u" ? wt = MozWebSocket : typeof global < "u" ? wt = global.WebSocket || global.MozWebSocket : typeof window < "u" ? wt = window.WebSocket || window.MozWebSocket : typeof self < "u" && (wt = self.WebSocket || self.MozWebSocket);
var Tt = wt, Y;
(function(e) {
	e.NervosDao = "NervosDao", e.Secp256k1Blake160 = "Secp256k1Blake160", e.Secp256k1Multisig = "Secp256k1Multisig", e.Secp256k1MultisigV2 = "Secp256k1MultisigV2", e.AnyoneCanPay = "AnyoneCanPay", e.TypeId = "TypeId", e.XUdt = "XUdt", e.JoyId = "JoyId", e.COTA = "COTA", e.PWLock = "PWLock", e.OmniLock = "OmniLock", e.NostrLock = "NostrLock", e.UniqueType = "UniqueType", e.AlwaysSuccess = "AlwaysSuccess", e.InputTypeProxyLock = "InputTypeProxyLock", e.OutputTypeProxyLock = "OutputTypeProxyLock", e.LockProxyLock = "LockProxyLock", e.SingleUseLock = "SingleUseLock", e.TypeBurnLock = "TypeBurnLock", e.EasyToDiscoverType = "EasyToDiscoverType", e.TimeLock = "TimeLock";
})(Y ||= {});
//#endregion
//#region node_modules/@ckb-ccc/core/dist/jsonRpc/transports/http.js
var Et = class {
	constructor(e, t = 3e4) {
		this.url = e, this.timeout = t;
	}
	async request(e) {
		let t = new AbortController(), n = setTimeout(() => t.abort(), this.timeout), r = await (await fetch(this.url, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify(e),
			signal: t.signal
		})).json();
		return clearTimeout(n), r;
	}
}, Dt = class {
	constructor(e, t = 3e4) {
		this.url = e, this.timeout = t, this.ongoing = /* @__PURE__ */ new Map();
	}
	request(e) {
		let t = (() => {
			if (this.socket && this.socket.readyState !== this.socket.CLOSING && this.socket.readyState !== this.socket.CLOSED && this.openSocket) return this.openSocket;
			let e = new Tt(this.url), t = ({ data: e }) => {
				let t = JSON.parse(e);
				if (typeof t != "object" || !t || typeof t.id != "number") throw Error(`Unknown response ${e}`);
				let n = t.id, r = this.ongoing.get(n);
				if (!r) return;
				let [i, a, o] = r;
				clearTimeout(o), this.ongoing.delete(n), i(t);
			}, n = () => {
				this.ongoing.forEach(([e, t, n]) => {
					clearTimeout(n), t(/* @__PURE__ */ Error("Connection closed"));
				}), this.ongoing.clear();
			};
			return e.onclose = n, e.onerror = n, e.onmessage = t, this.socket = e, this.openSocket = new Promise((t) => {
				e.readyState === e.OPEN ? t(e) : e.onopen = () => {
					t(e);
				};
			}), this.openSocket;
		})();
		return new Promise((n, r) => {
			let i = [
				n,
				r,
				setTimeout(() => {
					this.ongoing.delete(e.id), t.then((e) => e.close()).catch((e) => r(e)), r(/* @__PURE__ */ Error("Request timeout"));
				}, this.timeout)
			];
			this.ongoing.set(e.id, i), t.then((t) => {
				t.readyState === t.CLOSED || t.readyState === t.CLOSING ? (clearTimeout(i[2]), this.ongoing.delete(e.id), r(/* @__PURE__ */ Error("Connection closed"))) : t.send(JSON.stringify(e));
			}).catch((e) => r(e));
		});
	}
};
//#endregion
//#region node_modules/@ckb-ccc/core/dist/jsonRpc/transports/factory.js
function Ot(e, t) {
	return e.startsWith("wss://") || e.startsWith("ws://") ? new Dt(e, t?.timeout) : new Et(e, t?.timeout);
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/jsonRpc/transports/fallback.js
var kt = class {
	constructor(e) {
		this.transports = e, this.i = 0;
	}
	async request(e) {
		let t = 0;
		for (;;) try {
			return await this.transports[this.i % this.transports.length].request(e);
		} catch (e) {
			if (t += 1, this.i += 1, t >= this.transports.length) throw e;
		}
	}
};
//#endregion
//#region node_modules/@ckb-ccc/core/dist/jsonRpc/requestor.js
function At(e, t) {
	return t ? t(e) : e;
}
var jt = class {
	constructor(e, t, n) {
		this.url_ = e, this.onError = n, this.concurrent = 0, this.pending = [], this.id = 0, this.maxConcurrent = t?.maxConcurrent, this.transport = t?.transport ?? new kt(Array.from(new Set([e, ...t?.fallbacks ?? []]).values(), (e) => Ot(e, t)));
	}
	get url() {
		return this.url_;
	}
	async request(e, t, n, r) {
		let i = this.buildPayload(e, n ? await Promise.all(t.concat(Array.from(Array(Math.max(n.length - t.length, 0)))).map((e, t) => At(e, n[t]))) : t);
		try {
			return await At(await this.requestPayload(i), r);
		} catch (e) {
			if (!this.onError) throw e;
			await this.onError(e);
		}
	}
	async requestPayload(e) {
		this.maxConcurrent !== void 0 && this.concurrent >= this.maxConcurrent && await new Promise((e) => this.pending.push(e)), this.concurrent += 1;
		let t = await this.transport.request(e);
		if (--this.concurrent, this.pending.shift()?.(), t.id !== e.id) throw Error(`Id mismatched, got ${t.id}, expected ${e.id}`);
		if (t.error != null) throw t.error;
		return t.result;
	}
	buildPayload(e, t) {
		return {
			id: this.id++,
			method: e,
			params: t,
			jsonrpc: "2.0"
		};
	}
}, Mt = class e {
	static hashTypeFrom(e) {
		return Dn(e);
	}
	static hashTypeTo(e) {
		return e;
	}
	static depTypeFrom(e) {
		switch (Wn(e)) {
			case "code": return "code";
			case "depGroup": return "dep_group";
		}
	}
	static depTypeTo(e) {
		switch (e) {
			case "code": return "code";
			case "dep_group": return "depGroup";
		}
	}
	static scriptFrom(t) {
		let n = X.from(t);
		return {
			code_hash: n.codeHash,
			hash_type: e.hashTypeFrom(n.hashType),
			args: n.args
		};
	}
	static scriptTo(t) {
		return X.from({
			codeHash: t.code_hash,
			hashType: e.hashTypeTo(t.hash_type),
			args: t.args
		});
	}
	static outPointFrom(e) {
		let t = qn.from(e);
		return {
			index: Le(t.index),
			tx_hash: t.txHash
		};
	}
	static outPointTo(e) {
		return qn.from({
			index: e.index,
			txHash: e.tx_hash
		});
	}
	static cellInputFrom(t) {
		let n = tr.from(t);
		return {
			previous_output: e.outPointFrom(n.previousOutput),
			since: Le(n.since)
		};
	}
	static cellInputTo(t) {
		return tr.from({
			previousOutput: e.outPointTo(t.previous_output),
			since: t.since
		});
	}
	static cellOutputFrom(t, n) {
		let r = Jn.from(t, n);
		return {
			capacity: Le(r.capacity),
			lock: e.scriptFrom(r.lock),
			type: J(e.scriptFrom, r.type)
		};
	}
	static cellOutputTo(t) {
		return Jn.from({
			capacity: t.capacity,
			lock: e.scriptTo(t.lock),
			type: J(e.scriptTo, t.type)
		});
	}
	static cellDepFrom(t) {
		return {
			out_point: e.outPointFrom(t.outPoint),
			dep_type: e.depTypeFrom(t.depType)
		};
	}
	static cellDepTo(t) {
		return rr.from({
			outPoint: e.outPointTo(t.out_point),
			depType: e.depTypeTo(t.dep_type)
		});
	}
	static transactionFrom(t) {
		let n = cr.from(t);
		return {
			version: Le(n.version),
			cell_deps: n.cellDeps.map((t) => e.cellDepFrom(t)),
			header_deps: n.headerDeps,
			inputs: n.inputs.map((t) => e.cellInputFrom(t)),
			outputs: n.outputs.map((t) => e.cellOutputFrom(t)),
			outputs_data: n.outputsData,
			witnesses: n.witnesses
		};
	}
	static transactionTo(t) {
		return cr.from({
			version: t.version,
			cellDeps: t.cell_deps.map((t) => e.cellDepTo(t)),
			headerDeps: t.header_deps,
			inputs: t.inputs.map((t) => e.cellInputTo(t)),
			outputs: t.outputs.map((t) => e.cellOutputTo(t)),
			outputsData: t.outputs_data,
			witnesses: t.witnesses
		});
	}
	static transactionResponseTo({ cycles: t, tx_status: { status: n, block_number: r, block_hash: i, tx_index: a, reason: o }, transaction: s }) {
		if (s != null) return Ze.from({
			transaction: e.transactionTo(s),
			status: n,
			cycles: J(q, t),
			blockHash: J(K, i),
			blockNumber: J(q, r),
			txIndex: J(q, a),
			reason: o
		});
	}
	static blockHeaderTo(e) {
		let t = y(e.dao);
		return {
			compactTarget: q(e.compact_target),
			dao: {
				c: He(t.slice(0, 8)),
				ar: He(t.slice(8, 16)),
				s: He(t.slice(16, 24)),
				u: He(t.slice(24, 32))
			},
			epoch: $n(e.epoch),
			extraHash: e.extra_hash,
			hash: e.hash,
			nonce: q(e.nonce),
			number: q(e.number),
			parentHash: e.parent_hash,
			proposalsHash: e.proposals_hash,
			timestamp: q(e.timestamp),
			transactionsRoot: e.transactions_root,
			version: q(e.version)
		};
	}
	static blockUncleTo(t) {
		return {
			header: e.blockHeaderTo(t.header),
			proposals: t.proposals
		};
	}
	static blockTo(t) {
		return {
			header: e.blockHeaderTo(t.header),
			proposals: t.proposals,
			transactions: t.transactions.map((t) => e.transactionTo(t)),
			uncles: t.uncles.map((t) => e.blockUncleTo(t))
		};
	}
	static rangeFrom([e, t]) {
		return [Le(e), Le(t)];
	}
	static indexerSearchKeyFilterFrom(t) {
		return {
			script: J(e.scriptFrom, t.script),
			script_len_range: J(e.rangeFrom, t.scriptLenRange),
			output_data: t.outputData,
			output_data_filter_mode: t.outputDataSearchMode,
			output_data_len_range: J(e.rangeFrom, t.outputDataLenRange),
			output_capacity_range: J(e.rangeFrom, t.outputCapacityRange),
			block_range: J(e.rangeFrom, t.blockRange)
		};
	}
	static indexerSearchKeyFrom(t) {
		let n = $e.from(t);
		return {
			script: e.scriptFrom(n.script),
			script_type: n.scriptType,
			script_search_mode: n.scriptSearchMode,
			filter: J(e.indexerSearchKeyFilterFrom, n.filter),
			with_data: n.withData
		};
	}
	static findCellsResponseTo({ last_cursor: t, objects: n }) {
		return {
			lastCursor: t,
			cells: n.map((t) => Zn.from({
				outPoint: e.outPointTo(t.out_point),
				cellOutput: e.cellOutputTo(t.output),
				outputData: t.output_data ?? "0x"
			}))
		};
	}
	static indexerSearchKeyTransactionFrom(t) {
		let n = et.from(t);
		return {
			script: e.scriptFrom(n.script),
			script_type: n.scriptType,
			script_search_mode: n.scriptSearchMode,
			filter: J(e.indexerSearchKeyFilterFrom, n.filter),
			group_by_transaction: n.groupByTransaction
		};
	}
	static findTransactionsResponseTo({ last_cursor: e, objects: t }) {
		return t.length === 0 ? {
			lastCursor: e,
			transactions: []
		} : "io_index" in t[0] ? {
			lastCursor: e,
			transactions: t.map((e) => ({
				txHash: e.tx_hash,
				blockNumber: q(e.block_number),
				txIndex: q(e.tx_index),
				cellIndex: q(e.io_index),
				isInput: e.io_type === "input"
			}))
		} : {
			lastCursor: e,
			transactions: t.map((e) => ({
				txHash: e.tx_hash,
				blockNumber: q(e.block_number),
				txIndex: q(e.tx_index),
				cells: e.cells.map(([e, t]) => ({
					isInput: e === "input",
					cellIndex: q(t)
				}))
			}))
		};
	}
}, Nt = [
	["Resolve\\(Unknown\\(OutPoint\\((0x.*)\\)\\)\\)", (e, t) => new at(e, qn.fromBytes(t[1]))],
	["Verification\\(Error { kind: Script, inner: TransactionScriptError { source: (Inputs|Outputs)\\[([0-9]*)\\].(Lock|Type), cause: ValidationFailure: see error code (-?[0-9])* on page https://nervosnetwork\\.github\\.io/ckb-script-error-codes/by-(type|data)-hash/(.*)\\.html", (e, t) => new ot(e, t[3] === "Lock" ? "lock" : t[1] === "Inputs" ? "inputType" : "outputType", t[2], Number(t[4]), t[5] === "data" ? "data" : "type", t[6])],
	["Duplicated\\(Byte32\\((0x.*)\\)\\)", (e, t) => new st(e, t[1])],
	["RBFRejected\\(\"Tx's current fee is ([0-9]*), expect it to >= ([0-9]*) to replace old txs\"\\)", (e, t) => new ct(e, t[1], t[2])]
], Pt = class extends Ct {
	constructor(e, t) {
		super(t), this.getFeeRateStatistics = this.buildSender("get_fee_rate_statistics", [(e) => J(q, e)], ({ mean: e, median: t }) => ({
			mean: q(e),
			median: q(t)
		})), this.getTip = this.buildSender("get_tip_block_number", [], q), this.getTipHeader = this.buildSender("get_tip_header", [], (e) => J(Mt.blockHeaderTo, e)), this.getBlockByNumberNoCache = this.buildSender("get_block_by_number", [(e) => Le(q(e))], (e) => J(Mt.blockTo, e)), this.getBlockByHashNoCache = this.buildSender("get_block", [K], (e) => J(Mt.blockTo, e)), this.getHeaderByNumberNoCache = this.buildSender("get_header_by_number", [(e) => Le(q(e))], (e) => J(Mt.blockHeaderTo, e)), this.getHeaderByHashNoCache = this.buildSender("get_header", [K], (e) => J(Mt.blockHeaderTo, e)), this.estimateCycles = this.buildSender("estimate_cycles", [Mt.transactionFrom], ({ cycles: e }) => q(e)), this.sendTransactionDry = this.buildSender("test_tx_pool_accept", [Mt.transactionFrom], ({ cycles: e }) => q(e)), this.sendTransactionNoCache = this.buildSender("send_transaction", [Mt.transactionFrom, (e) => e ?? void 0], K), this.getTransactionNoCache = this.buildSender("get_transaction", [K], Mt.transactionResponseTo), this.findCellsPagedNoCache = this.buildSender("get_cells", [
			Mt.indexerSearchKeyFrom,
			(e) => e ?? "asc",
			(e) => Le(e ?? 10)
		], Mt.findCellsResponseTo), this.findTransactionsPaged = this.buildSender("get_transactions", [
			Mt.indexerSearchKeyTransactionFrom,
			(e) => e ?? "asc",
			(e) => Le(e ?? 10)
		], Mt.findTransactionsResponseTo), this.getCellsCapacity = this.buildSender("get_cells_capacity", [Mt.indexerSearchKeyFrom], ({ capacity: e }) => q(e)), this.requestor = t?.requestor ?? new jt(e, t, (e) => {
			if (typeof e != "object" || !e || !("data" in e) || typeof e.data != "string") throw e;
			let t = e;
			for (let [e, n] of Nt) {
				let r = t.data.match(e);
				if (r) throw n(t, r);
			}
			throw new it(t);
		});
	}
	get url() {
		return this.requestor.url;
	}
	getCellLiveNoCache(e, t, n) {
		return this.buildSender("get_live_cell", [Mt.outPointFrom], ({ cell: t }) => J(({ output: t, data: n }) => Zn.from({
			cellOutput: Mt.cellOutputTo(t),
			outputData: n?.content ?? "0x",
			outPoint: e
		}), t))(e, t ?? !0, n);
	}
	buildSender(e, t, n) {
		return async (...r) => this.requestor.request(e, r, t, n);
	}
}, Ft = Object.freeze({
	[Y.NervosDao]: {
		codeHash: "0x82d76d1b75fe2fd9a27dfbaa65a039221a380d76c926f378d3f81cf3e7e13f2e",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0x8f8c79eb6671709633fe6a46de93c0fedc9c1b8a6527a18d3983879542635c9f",
				index: 2
			},
			depType: "code"
		} }]
	},
	[Y.Secp256k1Blake160]: {
		codeHash: "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
				index: 0
			},
			depType: "depGroup"
		} }]
	},
	[Y.Secp256k1Multisig]: {
		codeHash: "0x5c5069eb0857efc65e1bca0c07df34c31663b3622fd3876c876320fc9634e2a8",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
				index: 1
			},
			depType: "depGroup"
		} }]
	},
	[Y.Secp256k1MultisigV2]: {
		codeHash: "0x36c971b8d41fbd94aabca77dc75e826729ac98447b46f91e00796155dddb0d29",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0x2eefdeb21f3a3edf697c28a52601b4419806ed60bb427420455cc29a090b26d5",
				index: 0
			},
			depType: "depGroup"
		} }]
	},
	[Y.AnyoneCanPay]: {
		codeHash: "0x3419a1c09eb2567f6552ee7a8ecffd64155cffe0f1796e6e61ec088d740c1356",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xec26b0f85ed839ece5f11c4c4e837ec359f5adc4420410f6453b1f6b60fb96a6",
				index: 0
			},
			depType: "depGroup"
		} }]
	},
	[Y.TypeId]: {
		codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
		hashType: "type",
		cellDeps: []
	},
	[Y.XUdt]: {
		codeHash: "0x25c29dc317811a6f6f3985a7a9ebc4838bd388d19d0feeecf0bcd60f6c0975bb",
		hashType: "type",
		cellDeps: [{
			cellDep: {
				outPoint: {
					txHash: "0xbf6fb538763efec2a70a6a3dcb7242787087e1030c4e7d86585bc63a9d337f5f",
					index: 0
				},
				depType: "code"
			},
			type: {
				codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
				hashType: "type",
				args: "0x44ec8b96663e06cc94c8c468a4d46d7d9af69eaf418f6390c9f11bb763dda0ae"
			}
		}]
	},
	[Y.JoyId]: {
		codeHash: "0xd23761b364210735c19c60561d213fb3beae2fd6172743719eff6920e020baac",
		hashType: "type",
		cellDeps: [
			{
				cellDep: {
					outPoint: {
						txHash: "0x4a596d31dc35e88fb1591debbf680b04a44b4a434e3a94453c21ea8950ffb4d9",
						index: 0
					},
					depType: "code"
				},
				type: {
					codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
					hashType: "type",
					args: "0x1c9fc299ba0570d077b4d7fb9acff1ccc0de69d369942d82678bae937c44ec30"
				}
			},
			{
				cellDep: {
					outPoint: {
						txHash: "0x4a596d31dc35e88fb1591debbf680b04a44b4a434e3a94453c21ea8950ffb4d9",
						index: 1
					},
					depType: "code"
				},
				type: {
					codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
					hashType: "type",
					args: "0x27f0d3ccdc2fcd52ae31fbacad5f86b97bc147d7093e4807cd6e3d21c1fe6841"
				}
			},
			{
				cellDep: {
					outPoint: {
						txHash: "0xf2c9dbfe7438a8c622558da8fa912d36755271ea469d3a25cb8d3373d35c8638",
						index: 1
					},
					depType: "code"
				},
				type: {
					codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
					hashType: "type",
					args: "0x0ac15fe5b2d059ec39de03f2d3159d5463abb918a1a07a9fa00d2b9c61d89ef3"
				}
			},
			{
				cellDep: {
					outPoint: {
						txHash: "0x95ecf9b41701b45d431657a67bbfa3f07ef7ceb53bf87097f3674e1a4a19ce62",
						index: 1
					},
					depType: "code"
				},
				type: {
					codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
					hashType: "type",
					args: "0xc7bafc5550ccad7cea32c27764f5df6aca4de547da65e3e67fa08477a1af7f5e"
				}
			},
			{
				cellDep: {
					outPoint: {
						txHash: "0x8b3255491f3c4dcc1cfca33d5c6bcaec5409efe4bbda243900f9580c47e0242e",
						index: 1
					},
					depType: "code"
				},
				type: {
					codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
					hashType: "type",
					args: "0x71decef9ca8725e64ec99a5521790d16b8d5daadb4989b45dd6ab51806a8c0e4"
				}
			}
		]
	},
	[Y.COTA]: {
		codeHash: "0x89cd8003a0eaf8e65e0c31525b7d1d5c1becefd2ea75bb4cff87810ae37764d8",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0x636a786001f87cb615acfcf408be0f9a1f077001f0bbc75ca54eadfe7e221713",
				index: 0
			},
			depType: "depGroup"
		} }]
	},
	[Y.PWLock]: {
		codeHash: "0x58c5f491aba6d61678b7cf7edf4910b1f5e00ec0cde2f42e0abb4fd9aff25a63",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
				index: 0
			},
			depType: "depGroup"
		} }, {
			cellDep: {
				outPoint: {
					txHash: "0x57a62003daeab9d54aa29b944fc3b451213a5ebdf2e232216a3cfed0dde61b38",
					index: 0
				},
				depType: "code"
			},
			type: {
				codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
				hashType: "type",
				args: "0xf6d90bfe3041d0fd7e01c45770241697f5f837974bd6ae1672a7ec0f9f523268"
			}
		}]
	},
	[Y.OmniLock]: {
		codeHash: "0xf329effd1c475a2978453c8600e1eaf0bc2087ee093c3ee64cc96ec6847752cb",
		hashType: "type",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
				index: 0
			},
			depType: "depGroup"
		} }, {
			cellDep: {
				outPoint: {
					txHash: "0xec18bf0d857c981c3d1f4e17999b9b90c484b303378e94de1a57b0872f5d4602",
					index: 0
				},
				depType: "code"
			},
			type: {
				codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
				hashType: "type",
				args: "0x761f51fc9cd6a504c32c6ae64b3746594d1af27629b427c5ccf6c9a725a89144"
			}
		}]
	},
	[Y.NostrLock]: {
		codeHash: "0x6ae5ee0cb887b2df5a9a18137315b9bdc55be8d52637b2de0624092d5f0c91d5",
		hashType: "type",
		cellDeps: [{
			cellDep: {
				outPoint: {
					txHash: "0xa2a434dcdbe280b9ed75bb7d6c7d68186a842456aba0fc506657dc5ed7c01d68",
					index: 0
				},
				depType: "code"
			},
			type: {
				codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
				hashType: "type",
				args: "0x8dc56c6f35f0c535e23ded1629b1f20535477a1b43e59f14617d11e32c50e0aa"
			}
		}]
	},
	[Y.UniqueType]: {
		codeHash: "0x8e341bcfec6393dcd41e635733ff2dca00a6af546949f70c57a706c0f344df8b",
		hashType: "type",
		cellDeps: [{
			cellDep: {
				outPoint: {
					txHash: "0xff91b063c78ed06f10a1ed436122bd7d671f9a72ef5f5fa28d05252c17cf4cef",
					index: 0
				},
				depType: "code"
			},
			type: {
				codeHash: "0x00000000000000000000000000000000000000000000000000545950455f4944",
				hashType: "type",
				args: "0xe04976b67600fd25ac50305f77b33aee2c12e3c18e63ece9119e5b32117884b5"
			}
		}]
	},
	[Y.AlwaysSuccess]: {
		codeHash: "0x3b521cc4b552f109d092d8cc468a8048acb53c5952dbe769d2b2f9cf6e47f7f1",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 0
			},
			depType: "code"
		} }]
	},
	[Y.InputTypeProxyLock]: {
		codeHash: "0x5123908965c711b0ffd8aec642f1ede329649bda1ebdca6bd24124d3796f768a",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 1
			},
			depType: "code"
		} }]
	},
	[Y.OutputTypeProxyLock]: {
		codeHash: "0x2df53b592db3ae3685b7787adcfef0332a611edb83ca3feca435809964c3aff2",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 2
			},
			depType: "code"
		} }]
	},
	[Y.LockProxyLock]: {
		codeHash: "0x5d41e32e224c15f152b7e6529100ebeac83b162f5f692a5365774dad2c1a1d02",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 3
			},
			depType: "code"
		} }]
	},
	[Y.SingleUseLock]: {
		codeHash: "0x8290467a512e5b9a6b816469b0edabba1f4ac474e28ffdd604c2a7c76446bbaf",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 4
			},
			depType: "code"
		} }]
	},
	[Y.TypeBurnLock]: {
		codeHash: "0xff78bae0abf17d7a404c0be0f9ad9c9185b3f88dcc60403453d5ba8e1f22f53a",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0xb4f171c9c9caf7401f54a8e56225ae21d95032150a87a4678eac3f66a3137b93",
				index: 5
			},
			depType: "code"
		} }]
	},
	[Y.EasyToDiscoverType]: {
		codeHash: "0xaba4430cc7110d699007095430a1faa72973edf2322ddbfd4d1d219cacf237af",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0x1b4ffcad55ecd36ffb2715b6816b83da73851f1a24fe594f263c4f34dad90792",
				index: 0
			},
			depType: "code"
		} }]
	},
	[Y.TimeLock]: {
		codeHash: "0x6fac4b2e89360a1e692efcddcb3a28656d8446549fb83da6d896db8b714f4451",
		hashType: "data1",
		cellDeps: [{ cellDep: {
			outPoint: {
				txHash: "0x1b4ffcad55ecd36ffb2715b6816b83da73851f1a24fe594f263c4f34dad90792",
				index: 1
			},
			depType: "code"
		} }]
	}
}), It = class extends Pt {
	constructor(e) {
		let t = Tt !== void 0;
		super(e?.url ?? (t ? "wss://testnet.ckb.dev/ws" : "https://testnet.ckb.dev/"), {
			...e,
			fallbacks: e?.fallbacks ?? (t ? [
				"wss://testnet.ckb.dev/ws",
				"https://testnet.ckb.dev/",
				"https://testnet.ckbapp.dev/"
			] : ["https://testnet.ckb.dev/", "https://testnet.ckbapp.dev/"])
		}), this.config = e;
	}
	get scripts() {
		return this.config?.scripts ?? Ft;
	}
	get addressPrefix() {
		return "ckt";
	}
	async getKnownScript(e) {
		let t = this.scripts[e];
		if (!t) throw Error(`No script information was found for ${e} on ${this.addressPrefix}`);
		return Xe.from(t);
	}
}, Lt = class e {
	constructor(e, t, n) {
		this.encode = e, this.decode = t, this.byteLength = n;
	}
	static from({ encode: t, decode: n, byteLength: r }) {
		return new e((e) => {
			let n = t(e);
			if (r !== void 0 && n.byteLength !== r) throw Error(`Codec.encode: expected byte length ${r}, got ${n.byteLength}`);
			return n;
		}, (e, t) => {
			let i = y(e);
			if (r !== void 0 && i.byteLength !== r) throw Error(`Codec.decode: expected byte length ${r}, got ${i.byteLength}`);
			return n(e, t);
		}, r);
	}
	map({ inMap: t, outMap: n }) {
		return new e((e) => this.encode(t ? t(e) : e), (e, t) => n ? n(this.decode(e, t)) : this.decode(e, t), this.byteLength);
	}
	mapIn(e) {
		return this.map({ inMap: e });
	}
	mapOut(e) {
		return this.map({ outMap: e });
	}
};
function Rt(e) {
	return Re(e, 4);
}
function zt(e) {
	return Number(Ve(e));
}
function Bt(e) {
	let t = e.byteLength;
	if (t === void 0) throw Error("fixedItemVec: itemCodec requires a byte length");
	return Lt.from({
		encode(t) {
			try {
				let n = [];
				g(n, Rt(t.length));
				for (let r of t) g(n, e.encode(r));
				return y(n);
			} catch (e) {
				throw Error(`fixedItemVec(${e?.toString()})`);
			}
		},
		decode(n, r) {
			let i = y(n);
			if (i.byteLength < 4) throw Error(`fixedItemVec: too short buffer, expected at least 4 bytes, but got ${i.byteLength}`);
			let a = 4 + zt(i.slice(0, 4)) * t;
			if (i.byteLength !== a) throw Error(`fixedItemVec: invalid buffer size, expected ${a}, but got ${i.byteLength}`);
			try {
				let n = [];
				for (let o = 4; o < a; o += t) n.push(e.decode(i.slice(o, o + t), r));
				return n;
			} catch (e) {
				throw Error(`fixedItemVec(${e?.toString()})`);
			}
		}
	});
}
function Vt(e) {
	return Lt.from({
		encode(t) {
			try {
				let n = 4 + t.length * 4, r = [], i = [];
				for (let a of t) {
					let t = e.encode(a);
					g(r, Rt(n)), g(i, t), n += t.byteLength;
				}
				return _(Rt(r.length + i.length + 4), r, i);
			} catch (e) {
				throw Error(`dynItemVec(${e?.toString()})`);
			}
		},
		decode(t, n) {
			let r = y(t);
			if (r.byteLength < 4) throw Error(`dynItemVec: too short buffer, expected at least 4 bytes, but got ${r.byteLength}`);
			let i = zt(r.slice(0, 4));
			if (i !== r.byteLength) throw Error(`dynItemVec: invalid buffer size, expected ${i}, but got ${r.byteLength}`);
			if (i === 4) return [];
			let a = (zt(r.slice(4, 8)) - 4) / 4, o = Array.from(Array(a), (e, t) => zt(r.slice(4 + t * 4, 8 + t * 4)));
			o.push(i);
			try {
				let t = [];
				for (let i = 0; i < o.length - 1; i++) {
					let a = o[i], s = o[i + 1], c = r.slice(a, s);
					t.push(e.decode(c, n));
				}
				return t;
			} catch (e) {
				throw Error(`dynItemVec(${e?.toString()})`);
			}
		}
	});
}
function Ht(e) {
	return e.byteLength === void 0 ? Vt(e) : Bt(e);
}
function Ut(e) {
	return Lt.from({
		encode(t) {
			if (t == null) return y([]);
			try {
				return e.encode(t);
			} catch (e) {
				throw Error(`option(${e?.toString()})`);
			}
		},
		decode(t, n) {
			if (y(t).byteLength !== 0) try {
				return e.decode(t, n);
			} catch (e) {
				throw Error(`option(${e?.toString()})`);
			}
		}
	});
}
function Wt(e) {
	return Lt.from({
		encode(t) {
			try {
				let n = y(e.encode(t));
				return _(Rt(n.byteLength), n);
			} catch (e) {
				throw Error(`byteVec(${e?.toString()})`);
			}
		},
		decode(t, n) {
			let r = y(t);
			if (r.byteLength < 4) throw Error(`byteVec: too short buffer, expected at least 4 bytes, but got ${r.byteLength}`);
			let i = zt(r.slice(0, 4));
			if (i !== r.byteLength - 4) throw Error(`byteVec: invalid buffer size, expected ${i}, but got ${r.byteLength}`);
			try {
				return e.decode(r.slice(4), n);
			} catch (e) {
				throw Error(`byteVec(${e?.toString()})`);
			}
		}
	});
}
function Gt(e) {
	let t = Object.keys(e);
	return Lt.from({
		encode(n) {
			let r = 4 + t.length * 4, i = [], a = [];
			for (let o of t) try {
				let t = e[o].encode(n[o]);
				g(i, Rt(r)), g(a, t), r += t.byteLength;
			} catch (e) {
				throw Error(`table.${o}(${e?.toString()})`);
			}
			return _(Rt(i.length + a.length + 4), i, a);
		},
		decode(n, r) {
			let i = y(n);
			if (i.byteLength < 4) throw Error(`table: too short buffer, expected at least 4 bytes, but got ${i.byteLength}`);
			let a = zt(i.slice(0, 4)), o = (zt(i.slice(4, 8)) - 4) / 4;
			if (a !== i.byteLength) throw Error(`table: invalid buffer size, expected ${a}, but got ${i.byteLength}`);
			if (o < t.length) throw Error(`table: invalid field count, expected ${t.length}, but got ${o}`);
			if (o > t.length && !r?.isExtraFieldIgnored) throw Error(`table: invalid field count, expected ${t.length}, but got ${o}, and extra fields are not allowed in the current configuration. If you want to ignore extra fields, set isExtraFieldIgnored to true.`);
			let s = t.map((e, t) => zt(i.slice(4 + t * 4, 8 + t * 4)));
			o > t.length ? s.push(zt(i.slice(4 + t.length * 4, 8 + t.length * 4))) : s.push(a);
			let c = {};
			for (let n = 0; n < s.length - 1; n++) {
				let a = s[n], o = s[n + 1], l = t[n], u = e[l], d = i.slice(a, o);
				try {
					Object.assign(c, { [l]: u.decode(d, r) });
				} catch (e) {
					throw Error(`table.${l}(${e?.toString()})`);
				}
			}
			return c;
		}
	});
}
function Kt(e) {
	let t = Object.values(e), n = Object.keys(e);
	return Lt.from({
		byteLength: t.reduce((e, t) => {
			if (t.byteLength === void 0) throw Error("struct: all fields must be fixed-size");
			return e + t.byteLength;
		}, 0),
		encode(t) {
			let r = [];
			for (let i of n) try {
				g(r, e[i].encode(t[i]));
			} catch (e) {
				throw Error(`struct.${i}(${e?.toString()})`);
			}
			return y(r);
		},
		decode(t, n) {
			let r = y(t), i = {}, a = 0;
			return Object.entries(e).forEach(([e, t]) => {
				let o = r.slice(a, a + t.byteLength);
				try {
					Object.assign(i, { [e]: t.decode(o, n) });
				} catch (t) {
					throw Error(`struct.${e}(${t.toString()})`);
				}
				a += t.byteLength;
			}), i;
		}
	});
}
function qt(e, t = !1) {
	return Lt.from({
		byteLength: e,
		encode: (n) => t ? Re(n, e) : Be(n, e),
		decode: (e) => t ? Ve(e) : Ue(e)
	});
}
function Jt(e, t = !1) {
	if (e > 4) throw Error("uintNumber: byteLength must be less than or equal to 4");
	return qt(e, t).map({ outMap: (e) => Number(e) });
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/molecule/entity.js
var Yt = class {
	static Base() {
		class e {
			static encode(e) {
				throw Error("encode not implemented, use @ccc.mol.codec to decorate your type");
			}
			static decode(e) {
				throw Error("decode not implemented, use @ccc.mol.codec to decorate your type");
			}
			static fromBytes(e) {
				throw Error("fromBytes not implemented, use @ccc.mol.codec to decorate your type");
			}
			static from(e) {
				throw Error("from not implemented");
			}
			toBytes() {
				return this.constructor.encode(this);
			}
			clone() {
				return this.constructor.fromBytes(this.toBytes());
			}
			eq(e) {
				return this === e ? !0 : b(this.toBytes(), (this.constructor?.from(e) ?? e).toBytes());
			}
			hash() {
				return Pe(this.toBytes());
			}
		}
		return e.encode = void 0, e.decode = void 0, e.fromBytes = void 0, e;
	}
};
function Xt(e) {
	return function(t, ...n) {
		return t.byteLength = e.byteLength, t.encode === void 0 && (t.encode = function(t) {
			return e.encode(t);
		}), t.decode === void 0 && (t.decode = function(n) {
			return t.from(e.decode(n));
		}), t.fromBytes === void 0 && (t.fromBytes = function(n) {
			return t.from(e.decode(n));
		}), t;
	};
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/molecule/predefined.js
var Zt = Jt(1, !0);
Ut(Zt), Ht(Zt);
var Qt = Jt(2, !0);
Jt(2);
var $t = Qt;
Ut($t), Ht($t);
var en = Jt(4, !0);
Jt(4);
var tn = en;
Ut(tn), Ht(tn);
var nn = qt(8, !0);
qt(8);
var rn = nn;
Ut(rn), Ht(rn);
var an = qt(16, !0);
qt(16);
var on = an;
Ut(on), Ht(on);
var sn = qt(32, !0);
qt(32);
var cn = sn;
Ut(cn), Ht(cn);
var ln = qt(64, !0);
qt(64);
var un = ln;
Ut(un), Ht(un);
var dn = Wt({
	encode: (e) => y(e),
	decode: (e) => K(e)
}), fn = Ut(dn), pn = Ht(dn), mn = Lt.from({
	byteLength: 1,
	encode: (e) => y(e ? [1] : [0]),
	decode: (e) => y(e)[0] !== 0
});
Ut(mn), Ht(mn);
var hn = Lt.from({
	byteLength: 4,
	encode: (e) => y(e),
	decode: (e) => K(e)
});
Ut(hn), Ht(hn);
var gn = Lt.from({
	byteLength: 8,
	encode: (e) => y(e),
	decode: (e) => K(e)
});
Ut(gn), Ht(gn);
var _n = Lt.from({
	byteLength: 16,
	encode: (e) => y(e),
	decode: (e) => K(e)
});
Ut(_n), Ht(_n);
var vn = Lt.from({
	byteLength: 32,
	encode: (e) => y(e),
	decode: (e) => K(e)
});
Ut(vn);
var yn = Ht(vn), bn = Wt({
	encode: (e) => y(e, "utf8"),
	decode: (e) => v(e, "utf8")
});
Ht(bn), Ut(bn);
//#endregion
//#region node_modules/@ckb-ccc/core/dist/ckb/script.advanced.js
var xn = {
	type: 1,
	data: 0,
	data1: 2,
	data2: 4
}, Sn = {
	1: "type",
	0: "data",
	2: "data1",
	4: "data2"
}, Cn = Object.keys(xn), wn = function(e, t, n, r) {
	var i = arguments.length, a = i < 3 ? t : r === null ? r = Object.getOwnPropertyDescriptor(t, n) : r, o;
	if (typeof Reflect == "object" && typeof Reflect.decorate == "function") a = Reflect.decorate(e, t, n, r);
	else for (var s = e.length - 1; s >= 0; s--) (o = e[s]) && (a = (i < 3 ? o(a) : i > 3 ? o(t, n, a) : o(t, n)) || a);
	return i > 3 && a && Object.defineProperty(t, n, a), a;
}, Tn, En = Lt.from({
	byteLength: 1,
	encode: On,
	decode: kn
});
function Dn(e) {
	let t = (() => {
		if (typeof e == "number") return Sn[e];
		if (typeof e == "bigint") return Sn[Number(e)];
		if (Cn.includes(e)) return e;
	})();
	if (t === void 0) throw Error(`Invalid hash type ${e}`);
	return t;
}
function On(e) {
	return y([xn[Dn(e)]]);
}
function kn(e) {
	return Sn[y(e)[0]];
}
var X = Tn = class extends Yt.Base() {
	constructor(e, t, n) {
		super(), this.codeHash = e, this.hashType = t, this.args = n;
	}
	get occupiedSize() {
		return 33 + y(this.args).length;
	}
	clone() {
		return new Tn(this.codeHash, this.hashType, this.args);
	}
	eq(e) {
		return e = Tn.from(e), this.args === e.args && this.codeHash === e.codeHash && this.hashType === e.hashType;
	}
	static from(e) {
		return e instanceof Tn ? e : new Tn(K(e.codeHash), Dn(e.hashType), K(e.args));
	}
	static async fromKnownScript(e, t, n) {
		let r = await e.getKnownScript(t);
		return new Tn(r.codeHash, r.hashType, K(n));
	}
};
X = Tn = wn([Xt(Gt({
	codeHash: vn,
	hashType: En,
	args: dn
}))], X);
var An = Ut(X);
Ht(X);
//#endregion
//#region node_modules/@ckb-ccc/core/dist/ckb/transaction.advanced.js
var jn = {
	code: 0,
	depGroup: 1
}, Mn = {
	0: "code",
	1: "depGroup"
}, Nn = class extends Error {
	constructor(e, t) {
		let n = q(e), r = t?.isForChange ?? !1;
		super(`Insufficient CKB, need ${bt(n)} extra CKB${r ? " for the change cell" : ""}`), this.amount = n, this.isForChange = r;
	}
}, Pn = class extends Error {
	constructor(e, t) {
		let n = q(e), r = X.from(t);
		super(`Insufficient coin, need ${n} extra coin`), this.amount = n, this.type = r;
	}
}, Fn = function(e, t, n, r) {
	var i = arguments.length, a = i < 3 ? t : r === null ? r = Object.getOwnPropertyDescriptor(t, n) : r, o;
	if (typeof Reflect == "object" && typeof Reflect.decorate == "function") a = Reflect.decorate(e, t, n, r);
	else for (var s = e.length - 1; s >= 0; s--) (o = e[s]) && (a = (i < 3 ? o(a) : i > 3 ? o(t, n, a) : o(t, n)) || a);
	return i > 3 && a && Object.defineProperty(t, n, a), a;
}, In, Ln, Rn, zn, Bn, Vn, Hn, Un = Lt.from({
	byteLength: 1,
	encode: Gn,
	decode: Kn
});
function Wn(e) {
	let t = typeof e == "number" ? Mn[e] : typeof e == "bigint" ? Mn[Number(e)] : e;
	if (t === void 0) throw Error(`Invalid dep type ${e}`);
	return t;
}
function Gn(e) {
	return y([jn[Wn(e)]]);
}
function Kn(e) {
	return Mn[y(e)[0]];
}
var qn = In = class extends Yt.Base() {
	constructor(e, t) {
		super(), this.txHash = e, this.index = t;
	}
	static from(e) {
		return e instanceof In ? e : new In(K(e.txHash), q(e.index));
	}
	clone() {
		return new In(this.txHash, this.index);
	}
	eq(e) {
		return e = In.from(e), this.txHash === e.txHash && this.index === e.index;
	}
};
qn = In = Fn([Xt(Kt({
	txHash: vn,
	index: tn
}))], qn);
var Jn = Ln = class extends Yt.Base() {
	constructor(e, t, n) {
		super(), this.capacity = e, this.lock = t, this.type = n;
	}
	get occupiedSize() {
		return 8 + this.lock.occupiedSize + (this.type?.occupiedSize ?? 0);
	}
	static from(e, t) {
		let n = e instanceof Ln ? e : new Ln(q(e.capacity ?? 0), X.from(e.lock), J(X.from, e.type));
		return n.capacity === 0n && t != null && (n.capacity = xt(n.occupiedSize + y(t).length)), n;
	}
	clone() {
		return new Ln(this.capacity, this.lock.clone(), this.type?.clone());
	}
};
Jn = Ln = Fn([Xt(Gt({
	capacity: rn,
	lock: X,
	type: An
}))], Jn);
var Yn = Ht(Jn), Xn = class e {
	constructor(e, t, n) {
		this.cellOutput = e, this.outputData = t, this.outPoint = n;
	}
	static from(t) {
		if (t instanceof e) return t;
		let n = K(t.outputData ?? "0x");
		return new e(Jn.from(t.cellOutput, n), n, J(qn.from, t.outPoint ?? t.previousOutput));
	}
	get occupiedSize() {
		return this.cellOutput.occupiedSize + y(this.outputData).byteLength;
	}
	get capacityFree() {
		return this.cellOutput.capacity - xt(this.occupiedSize);
	}
	async isNervosDao(e, t) {
		let { type: n } = this.cellOutput, r = await e.getKnownScript(Y.NervosDao);
		if (!n || n.codeHash !== r.codeHash || n.hashType !== r.hashType) return !1;
		let i = q(this.outputData) !== St;
		return !t || t === "deposited" && !i || t === "withdrew" && i;
	}
	clone() {
		return new e(this.cellOutput.clone(), this.outputData, this.outPoint?.clone());
	}
}, Zn = class e extends Xn {
	constructor(e, t, n) {
		super(t, n, e), this.outPoint = e;
	}
	static from(t) {
		return t instanceof e ? t : new e(qn.from(t.outPoint ?? t.previousOutput), Jn.from(t.cellOutput, t.outputData), K(t.outputData ?? "0x"));
	}
	async getDaoProfit(e) {
		if (!await this.isNervosDao(e, "withdrew")) return St;
		let { depositHeader: t, withdrawHeader: n } = await this.getNervosDaoInfo(e);
		if (!n || !t) throw Error(`Unable to get headers of a Nervos DAO cell ${this.outPoint.txHash}:${this.outPoint.index.toString()}`);
		return lr(this.capacityFree, t, n);
	}
	async getNervosDaoInfo(e) {
		if (!await this.isNervosDao(e)) return {};
		if (q(this.outputData) === 0n) {
			let t = await e.getCellWithHeader(this.outPoint);
			if (!t?.header) throw Error(`Unable to get header of a Nervos DAO deposited cell ${this.outPoint.txHash}:${this.outPoint.index.toString()}`);
			return { depositHeader: t.header };
		}
		let [t, n] = await Promise.all([e.getHeaderByNumber(Ve(this.outputData)), e.getCellWithHeader(this.outPoint)]);
		if (!n?.header || !t) throw Error(`Unable to get headers of a Nervos DAO withdrew cell ${this.outPoint.txHash}:${this.outPoint.index.toString()}`);
		return {
			depositHeader: t,
			withdrawHeader: n.header
		};
	}
	clone() {
		return new e(this.outPoint.clone(), this.cellOutput.clone(), this.outputData);
	}
};
function Qn(e) {
	return [
		q(e[0]),
		q(e[1]),
		q(e[2])
	];
}
function $n(e) {
	let t = q(K(e));
	return [
		t & q("0xffffff"),
		t >> q(24) & q("0xffff"),
		t >> q(40) & q("0xffff")
	];
}
var er = Rn = class extends Yt.Base() {
	constructor(e, t, n) {
		super(), this.relative = e, this.metric = t, this.value = n;
	}
	clone() {
		return new Rn(this.relative, this.metric, this.value);
	}
	static from(e) {
		return e instanceof Rn ? e : typeof e == "object" && "relative" in e ? new Rn(e.relative, e.metric, q(e.value)) : Rn.fromNum(e);
	}
	toNum() {
		return this.value | (this.relative === "absolute" ? St : q("0x8000000000000000")) | {
			blockNumber: q("0x0000000000000000"),
			epoch: q("0x2000000000000000"),
			timestamp: q("0x4000000000000000")
		}[this.metric];
	}
	static fromNum(e) {
		let t = q(e), n = t >> q(63) === 0n ? "absolute" : "relative", r = [
			"blockNumber",
			"epoch",
			"timestamp"
		][Number(t >> q(61) & q(3))], i = t & q("0x00ffffffffffffff");
		return new Rn(n, r, i);
	}
};
er = Rn = Fn([Xt(rn.mapIn((e) => er.from(e).toNum()))], er);
var tr = zn = class extends Yt.Base() {
	constructor(e, t, n, r) {
		super(), this.previousOutput = e, this.since = t, this.cellOutput = n, this.outputData = r;
	}
	static from(e) {
		return e instanceof zn ? e : new zn(qn.from("previousOutput" in e ? e.previousOutput : e.outPoint), er.from(e.since ?? 0).toNum(), J(Jn.from, e.cellOutput), J(K, e.outputData));
	}
	async getCell(e) {
		if (await this.completeExtraInfos(e), !this.cellOutput || !this.outputData) throw Error("Unable to complete input");
		return Zn.from({
			outPoint: this.previousOutput,
			cellOutput: this.cellOutput,
			outputData: this.outputData
		});
	}
	async completeExtraInfos(e) {
		if (this.cellOutput && this.outputData) return;
		let t = await e.getCell(this.previousOutput);
		t && (this.cellOutput = t.cellOutput, this.outputData = t.outputData);
	}
	async getExtraCapacity(e) {
		return (await this.getCell(e)).getDaoProfit(e);
	}
	clone() {
		return new zn(this.previousOutput.clone(), this.since, this.cellOutput?.clone(), this.outputData);
	}
};
tr = zn = Fn([Xt(Kt({
	since: er,
	previousOutput: qn
}).mapIn((e) => tr.from(e)))], tr);
var nr = Ht(tr), rr = Bn = class extends Yt.Base() {
	constructor(e, t) {
		super(), this.outPoint = e, this.depType = t;
	}
	static from(e) {
		return e instanceof Bn ? e : new Bn(qn.from(e.outPoint), Wn(e.depType));
	}
	clone() {
		return new Bn(this.outPoint.clone(), this.depType);
	}
};
rr = Bn = Fn([Xt(Kt({
	outPoint: qn,
	depType: Un
}))], rr);
var ir = Ht(rr), ar = Vn = class extends Yt.Base() {
	constructor(e, t, n) {
		super(), this.lock = e, this.inputType = t, this.outputType = n;
	}
	static from(e) {
		return e instanceof Vn ? e : new Vn(J(K, e.lock), J(K, e.inputType), J(K, e.outputType));
	}
};
ar = Vn = Fn([Xt(Gt({
	lock: fn,
	inputType: fn,
	outputType: fn
}))], ar);
function or(e) {
	let t = y(e).slice(0, 16);
	return t.length === 0 ? St : Ve(t);
}
var sr = Gt({
	version: tn,
	cellDeps: ir,
	headerDeps: yn,
	inputs: nr,
	outputs: Yn,
	outputsData: pn
}), cr = Hn = class extends Yt.Base() {
	constructor(e, t, n, r, i, a, o) {
		super(), this.version = e, this.cellDeps = t, this.headerDeps = n, this.inputs = r, this.outputs = i, this.outputsData = a, this.witnesses = o;
	}
	static default() {
		return new Hn(0n, [], [], [], [], [], []);
	}
	copy(e) {
		let t = Hn.from(e);
		this.version = t.version, this.cellDeps = t.cellDeps, this.headerDeps = t.headerDeps, this.inputs = t.inputs, this.outputs = t.outputs, this.outputsData = t.outputsData, this.witnesses = t.witnesses;
	}
	clone() {
		return new Hn(this.version, this.cellDeps.map((e) => e.clone()), this.headerDeps.map((e) => e), this.inputs.map((e) => e.clone()), this.outputs.map((e) => e.clone()), this.outputsData.map((e) => e), this.witnesses.map((e) => e));
	}
	static from(e) {
		if (e instanceof Hn) return e;
		let t = e.outputs?.map((t, n) => Jn.from(t, e.outputsData?.[n] ?? [])) ?? [], n = t.map((t, n) => K(e.outputsData?.[n] ?? "0x"));
		return e.outputsData != null && n.length < e.outputsData.length && n.push(...e.outputsData.slice(n.length).map((e) => K(e))), new Hn(q(e.version ?? 0), e.cellDeps?.map((e) => rr.from(e)) ?? [], e.headerDeps?.map(K) ?? [], e.inputs?.map((e) => tr.from(e)) ?? [], t, n, e.witnesses?.map(K) ?? []);
	}
	static fromLumosSkeleton(e) {
		return Hn.from({
			version: 0n,
			cellDeps: e.cellDeps.toArray(),
			headerDeps: e.headerDeps.toArray(),
			inputs: e.inputs.toArray().map((t, n) => {
				if (!t.outPoint) throw Error("outPoint is required in input");
				return tr.from({
					previousOutput: t.outPoint,
					since: e.inputSinces.get(n, "0x0"),
					cellOutput: t.cellOutput,
					outputData: t.data
				});
			}),
			outputs: e.outputs.toArray().map((e) => e.cellOutput),
			outputsData: e.outputs.toArray().map((e) => e.data),
			witnesses: e.witnesses.toArray()
		});
	}
	stringify() {
		return JSON.stringify(this, (e, t) => typeof t == "bigint" ? Le(t) : t);
	}
	rawToBytes() {
		return sr.encode(this);
	}
	hash() {
		return Pe(this.rawToBytes());
	}
	hashFull() {
		return Pe(this.toBytes());
	}
	static hashWitnessToHasher(e, t) {
		let n = y(K(e));
		t.update(Re(n.length, 8)), t.update(n);
	}
	async getSignHashInfo(e, t, n = new Ne()) {
		let r = X.from(e), i = -1;
		n.update(this.hash());
		for (let e = 0; e < this.witnesses.length; e += 1) {
			let a = this.inputs[e];
			if (a) {
				let { cellOutput: n } = await a.getCell(t);
				if (!r.eq(n.lock)) continue;
				i === -1 && (i = e);
			}
			if (i === -1) return;
			Hn.hashWitnessToHasher(this.witnesses[e], n);
		}
		if (i !== -1) return {
			message: n.digest(),
			position: i
		};
	}
	async findInputIndexByLockId(e, t) {
		let n = X.from({
			...e,
			args: "0x"
		});
		for (let e = 0; e < this.inputs.length; e += 1) {
			let { cellOutput: r } = await this.inputs[e].getCell(t);
			if (n.codeHash === r.lock.codeHash && n.hashType === r.lock.hashType) return e;
		}
	}
	async findInputIndexByLock(e, t) {
		let n = X.from(e);
		for (let e = 0; e < this.inputs.length; e += 1) {
			let { cellOutput: r } = await this.inputs[e].getCell(t);
			if (n.eq(r.lock)) return e;
		}
	}
	async findLastInputIndexByLock(e, t) {
		let n = X.from(e);
		for (let e = this.inputs.length - 1; e >= 0; --e) {
			let { cellOutput: r } = await this.inputs[e].getCell(t);
			if (n.eq(r.lock)) return e;
		}
	}
	addCellDeps(...e) {
		e.flat().forEach((e) => {
			let t = rr.from(e);
			this.cellDeps.some((e) => e.eq(t)) || this.cellDeps.push(t);
		});
	}
	addCellDepsAtStart(...e) {
		e.flat().forEach((e) => {
			let t = rr.from(e);
			this.cellDeps.some((e) => e.eq(t)) || this.cellDeps.unshift(t);
		});
	}
	async addCellDepInfos(e, ...t) {
		this.addCellDeps(await e.getCellDeps(...t));
	}
	async addCellDepsOfKnownScripts(e, ...t) {
		await Promise.all(t.flat().map(async (t) => this.addCellDepInfos(e, (await e.getKnownScript(t)).cellDeps)));
	}
	setOutputDataAt(e, t) {
		this.outputsData.length < e && this.outputsData.push(...Array.from(Array(e - this.outputsData.length), () => "0x")), this.outputsData[e] = K(t);
	}
	getInput(e) {
		return this.inputs[Number(q(e))];
	}
	addInput(e) {
		return this.witnesses.length > this.inputs.length && this.witnesses.splice(this.inputs.length, 0, "0x"), this.inputs.push(tr.from(e));
	}
	getOutput(e) {
		let t = Number(q(e));
		if (!(t >= this.outputs.length)) return Xn.from({
			cellOutput: this.outputs[t],
			outputData: this.outputsData[t] ?? "0x"
		});
	}
	get outputCells() {
		let { outputs: e, outputsData: t } = this;
		function* n() {
			for (let n = 0; n < e.length; n++) yield Xn.from({
				cellOutput: e[n],
				outputData: t[n] ?? "0x"
			});
		}
		return n();
	}
	addOutput(e, t) {
		let n = "cellOutput" in e ? Xn.from(e) : Xn.from({
			cellOutput: e,
			outputData: t
		}), r = this.outputs.push(n.cellOutput);
		return this.setOutputDataAt(r - 1, n.outputData), r;
	}
	getWitnessArgsAt(e) {
		let t = this.witnesses[e];
		return (t ?? "0x") === "0x" ? void 0 : ar.fromBytes(t);
	}
	setWitnessArgsAt(e, t) {
		this.setWitnessAt(e, t.toBytes());
	}
	setWitnessAt(e, t) {
		this.witnesses.length < e && this.witnesses.push(...Array.from(Array(e - this.witnesses.length), () => "0x")), this.witnesses[e] = K(t);
	}
	async prepareSighashAllWitness(e, t, n) {
		let r = await this.findInputIndexByLock(e, n);
		if (r === void 0) return;
		let i = this.getWitnessArgsAt(r) ?? ar.from({});
		i.lock = K(Array.from(Array(t), () => 0)), this.setWitnessArgsAt(r, i);
	}
	async getInputsCapacityExtra(e) {
		return qe(this.inputs, async (t, n) => t + await n.getExtraCapacity(e), q(0));
	}
	async getInputsCapacity(e) {
		return await qe(this.inputs, async (t, n) => {
			let { cellOutput: { capacity: r } } = await n.getCell(e);
			return t + r;
		}, q(0)) + await this.getInputsCapacityExtra(e);
	}
	getOutputsCapacity() {
		return this.outputs.reduce((e, { capacity: t }) => e + t, q(0));
	}
	async getInputsUdtBalance(e, t) {
		return qe(this.inputs, async (n, r) => {
			let { cellOutput: i, outputData: a } = await r.getCell(e);
			if (i.type?.eq(t)) return n + or(a);
		}, q(0));
	}
	getOutputsUdtBalance(e) {
		return this.outputs.reduce((t, n, r) => n.type?.eq(e) ? t + or(this.outputsData[r]) : t, q(0));
	}
	async completeInputs(e, t, n, r) {
		let i = [], a = r, o = !1;
		for await (let r of e.findCells(t, !0)) {
			if (this.inputs.some(({ previousOutput: e }) => e.eq(r.outPoint))) continue;
			let e = i.push(r), t = await Promise.resolve(n(a, r, e - 1, i));
			if (t === void 0) {
				o = !0;
				break;
			}
			a = t;
		}
		return i.forEach((e) => this.addInput(e)), o ? { addedCount: i.length } : {
			addedCount: i.length,
			accumulated: a
		};
	}
	async completeInputsByCapacity(e, t, n) {
		let r = this.getOutputsCapacity() + q(t ?? 0), i = await this.getInputsCapacity(e.client);
		if (i >= r) return 0;
		let { addedCount: a, accumulated: o } = await this.completeInputs(e, n ?? {
			scriptLenRange: [0, 1],
			outputDataLenRange: [0, 1]
		}, (e, { cellOutput: { capacity: t } }) => {
			let n = e + t;
			return n >= r ? void 0 : n;
		}, i);
		if (o === void 0) return a;
		throw new Nn(r - o);
	}
	async completeInputsAll(e, t) {
		let { addedCount: n } = await this.completeInputs(e, t ?? {
			scriptLenRange: [0, 1],
			outputDataLenRange: [0, 1]
		}, (e, { cellOutput: { capacity: t } }) => e + t, St);
		return n;
	}
	async completeInputsByUdt(e, t, n) {
		let r = this.getOutputsUdtBalance(t) + q(n ?? 0);
		if (r === q(0)) return 0;
		let [i, a] = await qe(this.inputs, async ([n, r], i) => {
			let { cellOutput: a, outputData: o } = await i.getCell(e.client);
			if (a.type?.eq(t)) return [n + or(o), r + 1];
		}, [q(0), 0]);
		if (i === r || i >= r && a >= 2) return 0;
		let { addedCount: o, accumulated: s } = await this.completeInputs(e, {
			script: t,
			outputDataLenRange: [16, q("0xffffffff")]
		}, (e, { outputData: t }, n, i) => {
			let o = e + or(t);
			return o === r || o >= r && a + i.length >= 2 ? void 0 : o;
		}, i);
		if (s === void 0 || s >= r) return o;
		throw new Pn(r - s, t);
	}
	async completeInputsAddOne(e, t) {
		let { addedCount: n, accumulated: r } = await this.completeInputs(e, t ?? {
			scriptLenRange: [0, 1],
			outputDataLenRange: [0, 1]
		}, () => void 0, !0);
		if (r === void 0) return n;
		throw Error("Insufficient CKB, need at least one new cell");
	}
	async completeInputsAtLeastOne(e, t) {
		return this.inputs.length > 0 ? 0 : this.completeInputsAddOne(e, t);
	}
	async getFee(e) {
		return await this.getInputsCapacity(e) - this.getOutputsCapacity();
	}
	async getFeeRate(e) {
		return await this.getFee(e) * q(1e3) / q(this.toBytes().length + 4);
	}
	estimateFee(e) {
		return (q(this.toBytes().length + 4) * q(e) + q(999)) / q(1e3);
	}
	async completeFee(e, t, n, r, i) {
		let a = n ?? await e.client.getFeeRate(i?.feeRateBlockRange, i);
		await this.getInputsCapacity(e.client);
		let o = St, s = St, c = 0;
		for (;;) {
			c += await (async () => {
				if (!(i?.shouldAddInputs ?? !0)) return 0;
				try {
					return await this.completeInputsByCapacity(e, o + s, r);
				} catch (e) {
					throw e instanceof Nn && s !== 0n ? new Nn(e.amount, { isForChange: !0 }) : e;
				}
			})();
			let n = await this.getFee(e.client);
			if (n < o + s) throw new Nn(o + s - n, { isForChange: s !== St });
			if (await e.prepareTransaction(this), o === 0n && (o = this.estimateFee(a)), n === o) return [c, !1];
			let l = this.clone(), u = q(await Promise.resolve(t(l, n - o)));
			if (u > 0n) {
				s = u;
				continue;
			}
			if (await l.getFee(e.client) !== o) throw Error("The change function doesn't use all available capacity");
			await e.prepareTransaction(l);
			let d = l.estimateFee(a);
			if (o > d) throw Error("The change function removed existed transaction data");
			if (o === d) return this.copy(l), [c, !0];
			o = d;
		}
	}
	completeFeeChangeToLock(e, t, n, r, i) {
		let a = X.from(t);
		return this.completeFee(e, (e, t) => {
			let n = Jn.from({
				capacity: 0,
				lock: a
			}), r = xt(n.occupiedSize);
			return t < r ? r : (n.capacity = t, e.addOutput(n), 0);
		}, n, r, i);
	}
	async completeFeeBy(e, t, n, r) {
		let { script: i } = await e.getRecommendedAddressObj();
		return this.completeFeeChangeToLock(e, i, t, n, r);
	}
	completeFeeChangeToOutput(e, t, n, r, i) {
		let a = Number(q(t));
		if (!this.outputs[a]) throw Error("Non-existed output to change");
		return this.completeFee(e, (e, t) => (e.outputs[a].capacity += t, 0), n, r, i);
	}
};
cr = Hn = Fn([Xt(Gt({
	raw: sr,
	witnesses: pn
}).mapIn((e) => {
	let t = cr.from(e);
	return {
		raw: t,
		witnesses: t.witnesses
	};
}).mapOut((e) => cr.from({
	...e.raw,
	witnesses: e.witnesses
})))], cr);
function lr(e, t, n) {
	let r = tt.from(t), i = tt.from(n), a = q(e);
	return a * i.dao.ar / r.dao.ar - a;
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/address/address.advanced.js
var ur = f();
function dr(e) {
	try {
		let { words: t, prefix: n } = ur.bech32m.decode(e, mr), r = ur.bech32m.fromWords(t), i = r[0], a = r.slice(1);
		if (i === pr.Full) return {
			prefix: n,
			format: pr.Full,
			payload: a
		};
	} catch {}
	try {
		let { prefix: t, words: n } = ur.bech32.decode(e, mr), r = ur.bech32.fromWords(n), i = r[0], a = r.slice(1);
		if ([
			pr.FullData,
			pr.FullType,
			pr.Short
		].includes(i)) return {
			prefix: t,
			format: i,
			payload: a
		};
	} catch {}
	throw Error(`Unknown address format ${e}`);
}
async function fr(e, t, n, r) {
	if (t === pr.Full) {
		if (n.length < 33) throw Error(`Invalid full address without enough payload ${K(n)}`);
		return {
			script: {
				codeHash: n.slice(0, 32),
				hashType: kn(n.slice(32, 33)),
				args: n.slice(33)
			},
			prefix: e
		};
	}
	if (t === pr.FullData) {
		if (n.length < 32) throw Error(`Invalid full data address without enough payload ${K(n)}`);
		return {
			script: {
				codeHash: n.slice(0, 32),
				hashType: "data",
				args: n.slice(32)
			},
			prefix: e
		};
	}
	if (t === pr.FullType) {
		if (n.length < 32) throw Error(`Invalid full type address without enough payload ${K(n)}`);
		return {
			script: {
				codeHash: n.slice(0, 32),
				hashType: "type",
				args: n.slice(32)
			},
			prefix: e
		};
	}
	if (n.length !== 21) throw Error(`Invalid short address without enough payload ${K(n)}`);
	let i = [
		Y.Secp256k1Blake160,
		Y.Secp256k1Multisig,
		Y.AnyoneCanPay
	][n[0]];
	if (i === void 0) throw Error(`Invalid short address with unknown script ${K(n)}`);
	return {
		script: await X.fromKnownScript(r, i, n.slice(1)),
		prefix: e
	};
}
var pr;
(function(e) {
	e[e.Full = 0] = "Full", e[e.Short = 1] = "Short", e[e.FullData = 2] = "FullData", e[e.FullType = 4] = "FullType";
})(pr ||= {});
var mr = 1023, hr = class e {
	constructor(e, t) {
		this.script = e, this.prefix = t;
	}
	static from(t) {
		return t instanceof e ? t : new e(X.from(t.script), t.prefix);
	}
	static async fromString(t, n) {
		let { prefix: r, format: i, payload: a } = dr(t), o = n[r] ?? n;
		if (!o) throw Error(`Unknown address prefix ${r}`);
		let s = o.addressPrefix;
		if (s !== r) throw Error(`Unknown address prefix ${r}, expected ${s}`);
		return e.from(await fr(r, i, a, o));
	}
	static fromScript(t, n) {
		return e.from({
			script: t,
			prefix: n.addressPrefix
		});
	}
	static async fromKnownScript(t, n, r) {
		return e.from({
			script: await X.fromKnownScript(t, n, r),
			prefix: t.addressPrefix
		});
	}
	toString() {
		let e = _([pr.Full], y(this.script.codeHash), On(this.script.hashType), y(this.script.args));
		return ur.bech32m.encode(this.prefix, ur.bech32m.toWords(e), mr);
	}
}, gr = class extends R {
	constructor(e, t) {
		super(), this.finished = !1, this.destroyed = !1, T(e);
		let n = L(t);
		if (this.iHash = e.create(), typeof this.iHash.update != "function") throw Error("Expected instance of class which extends utils.Hash");
		this.blockLen = this.iHash.blockLen, this.outputLen = this.iHash.outputLen;
		let r = this.blockLen, i = new Uint8Array(r);
		i.set(n.length > r ? e.create().update(n).digest() : n);
		for (let e = 0; e < i.length; e++) i[e] ^= 54;
		this.iHash.update(i), this.oHash = e.create();
		for (let e = 0; e < i.length; e++) i[e] ^= 106;
		this.oHash.update(i), O(i);
	}
	update(e) {
		return E(this), this.iHash.update(e), this;
	}
	digestInto(e) {
		E(this), w(e, this.outputLen), this.finished = !0, this.iHash.digestInto(e), this.oHash.update(e), this.oHash.digestInto(e), this.destroy();
	}
	digest() {
		let e = new Uint8Array(this.oHash.outputLen);
		return this.digestInto(e), e;
	}
	_cloneInto(e) {
		e ||= Object.create(Object.getPrototypeOf(this), {});
		let { oHash: t, iHash: n, finished: r, destroyed: i, blockLen: a, outputLen: o } = this;
		return e = e, e.finished = r, e.destroyed = i, e.blockLen = a, e.outputLen = o, e.oHash = t._cloneInto(e.oHash), e.iHash = n._cloneInto(e.iHash), e;
	}
	clone() {
		return this._cloneInto();
	}
	destroy() {
		this.destroyed = !0, this.oHash.destroy(), this.iHash.destroy();
	}
}, _r = (e, t, n) => new gr(e, t).update(n).digest();
_r.create = (e, t) => new gr(e, t);
//#endregion
//#region node_modules/@noble/hashes/esm/sha2.js
var vr = /* @__PURE__ */ Uint32Array.from([
	1116352408,
	1899447441,
	3049323471,
	3921009573,
	961987163,
	1508970993,
	2453635748,
	2870763221,
	3624381080,
	310598401,
	607225278,
	1426881987,
	1925078388,
	2162078206,
	2614888103,
	3248222580,
	3835390401,
	4022224774,
	264347078,
	604807628,
	770255983,
	1249150122,
	1555081692,
	1996064986,
	2554220882,
	2821834349,
	2952996808,
	3210313671,
	3336571891,
	3584528711,
	113926993,
	338241895,
	666307205,
	773529912,
	1294757372,
	1396182291,
	1695183700,
	1986661051,
	2177026350,
	2456956037,
	2730485921,
	2820302411,
	3259730800,
	3345764771,
	3516065817,
	3600352804,
	4094571909,
	275423344,
	430227734,
	506948616,
	659060556,
	883997877,
	958139571,
	1322822218,
	1537002063,
	1747873779,
	1955562222,
	2024104815,
	2227730452,
	2361852424,
	2428436474,
	2756734187,
	3204031479,
	3329325298
]), yr = /* @__PURE__ */ new Uint32Array(64), br = class extends me {
	constructor(e = 32) {
		super(64, e, 8, !1), this.A = V[0] | 0, this.B = V[1] | 0, this.C = V[2] | 0, this.D = V[3] | 0, this.E = V[4] | 0, this.F = V[5] | 0, this.G = V[6] | 0, this.H = V[7] | 0;
	}
	get() {
		let { A: e, B: t, C: n, D: r, E: i, F: a, G: o, H: s } = this;
		return [
			e,
			t,
			n,
			r,
			i,
			a,
			o,
			s
		];
	}
	set(e, t, n, r, i, a, o, s) {
		this.A = e | 0, this.B = t | 0, this.C = n | 0, this.D = r | 0, this.E = i | 0, this.F = a | 0, this.G = o | 0, this.H = s | 0;
	}
	process(e, t) {
		for (let n = 0; n < 16; n++, t += 4) yr[n] = e.getUint32(t, !1);
		for (let e = 16; e < 64; e++) {
			let t = yr[e - 15], n = yr[e - 2], r = te(t, 7) ^ te(t, 18) ^ t >>> 3;
			yr[e] = (te(n, 17) ^ te(n, 19) ^ n >>> 10) + yr[e - 7] + r + yr[e - 16] | 0;
		}
		let { A: n, B: r, C: i, D: a, E: o, F: s, G: c, H: l } = this;
		for (let e = 0; e < 64; e++) {
			let t = te(o, 6) ^ te(o, 11) ^ te(o, 25), u = l + t + fe(o, s, c) + vr[e] + yr[e] | 0, d = (te(n, 2) ^ te(n, 13) ^ te(n, 22)) + pe(n, r, i) | 0;
			l = c, c = s, s = o, o = a + u | 0, a = i, i = r, r = n, n = u + d | 0;
		}
		n = n + this.A | 0, r = r + this.B | 0, i = i + this.C | 0, a = a + this.D | 0, o = o + this.E | 0, s = s + this.F | 0, c = c + this.G | 0, l = l + this.H | 0, this.set(n, r, i, a, o, s, c, l);
	}
	roundClean() {
		O(yr);
	}
	destroy() {
		this.set(0, 0, 0, 0, 0, 0, 0, 0), O(this.buffer);
	}
}, xr = U((/* @__PURE__ */ "0x428a2f98d728ae22.0x7137449123ef65cd.0xb5c0fbcfec4d3b2f.0xe9b5dba58189dbbc.0x3956c25bf348b538.0x59f111f1b605d019.0x923f82a4af194f9b.0xab1c5ed5da6d8118.0xd807aa98a3030242.0x12835b0145706fbe.0x243185be4ee4b28c.0x550c7dc3d5ffb4e2.0x72be5d74f27b896f.0x80deb1fe3b1696b1.0x9bdc06a725c71235.0xc19bf174cf692694.0xe49b69c19ef14ad2.0xefbe4786384f25e3.0x0fc19dc68b8cd5b5.0x240ca1cc77ac9c65.0x2de92c6f592b0275.0x4a7484aa6ea6e483.0x5cb0a9dcbd41fbd4.0x76f988da831153b5.0x983e5152ee66dfab.0xa831c66d2db43210.0xb00327c898fb213f.0xbf597fc7beef0ee4.0xc6e00bf33da88fc2.0xd5a79147930aa725.0x06ca6351e003826f.0x142929670a0e6e70.0x27b70a8546d22ffc.0x2e1b21385c26c926.0x4d2c6dfc5ac42aed.0x53380d139d95b3df.0x650a73548baf63de.0x766a0abb3c77b2a8.0x81c2c92e47edaee6.0x92722c851482353b.0xa2bfe8a14cf10364.0xa81a664bbc423001.0xc24b8b70d0f89791.0xc76c51a30654be30.0xd192e819d6ef5218.0xd69906245565a910.0xf40e35855771202a.0x106aa07032bbd1b8.0x19a4c116b8d2d0c8.0x1e376c085141ab53.0x2748774cdf8eeb99.0x34b0bcb5e19b48a8.0x391c0cb3c5c95a63.0x4ed8aa4ae3418acb.0x5b9cca4f7763e373.0x682e6ff3d6b2b8a3.0x748f82ee5defb2fc.0x78a5636f43172f60.0x84c87814a1f0ab72.0x8cc702081a6439ec.0x90befffa23631e28.0xa4506cebde82bde9.0xbef9a3f7b2c67915.0xc67178f2e372532b.0xca273eceea26619c.0xd186b8c721c0c207.0xeada7dd6cde0eb1e.0xf57d4f7fee6ed178.0x06f067aa72176fba.0x0a637dc5a2c898a6.0x113f9804bef90dae.0x1b710b35131c471b.0x28db77f523047d84.0x32caab7b40c72493.0x3c9ebe0a15c9bebc.0x431d67c49c100d4c.0x4cc5d4becb3e42b6.0x597f299cfc657e2a.0x5fcb6fab3ad6faec.0x6c44198c4a475817".split(".")).map((e) => BigInt(e)));
xr[0], xr[1];
var Sr = /* @__PURE__ */ le(() => new br()), Cr = /* @__PURE__ */ BigInt(0), wr = /* @__PURE__ */ BigInt(1);
function Tr(e, t = "") {
	if (typeof e != "boolean") {
		let n = t && `"${t}"`;
		throw Error(n + "expected boolean, got type=" + typeof e);
	}
	return e;
}
function Er(e, t, n = "") {
	let r = S(e), i = e?.length, a = t !== void 0;
	if (!r || a && i !== t) {
		let o = n && `"${n}" `, s = a ? ` of length ${t}` : "", c = r ? `length=${i}` : `type=${typeof e}`;
		throw Error(o + "expected Uint8Array" + s + ", got " + c);
	}
	return e;
}
function Dr(e) {
	let t = e.toString(16);
	return t.length & 1 ? "0" + t : t;
}
function Or(e) {
	if (typeof e != "string") throw Error("hex string expected, got " + typeof e);
	return e === "" ? Cr : BigInt("0x" + e);
}
function kr(e) {
	return Or(ae(e));
}
function Ar(e) {
	return w(e), Or(ae(Uint8Array.from(e).reverse()));
}
function jr(e, t) {
	return se(e.toString(16).padStart(t * 2, "0"));
}
function Mr(e, t) {
	return jr(e, t).reverse();
}
function Nr(e, t, n) {
	let r;
	if (typeof t == "string") try {
		r = se(t);
	} catch (t) {
		throw Error(e + " must be hex string or Uint8Array, cause: " + t);
	}
	else if (S(t)) r = Uint8Array.from(t);
	else throw Error(e + " must be hex string or Uint8Array");
	let i = r.length;
	if (typeof n == "number" && i !== n) throw Error(e + " of length " + n + " expected, got " + i);
	return r;
}
var Pr = (e) => typeof e == "bigint" && Cr <= e;
function Fr(e, t, n) {
	return Pr(e) && Pr(t) && Pr(n) && t <= e && e < n;
}
function Ir(e, t, n, r) {
	if (!Fr(t, n, r)) throw Error("expected valid " + e + ": " + n + " <= n < " + r + ", got " + t);
}
function Lr(e) {
	let t;
	for (t = 0; e > Cr; e >>= wr, t += 1);
	return t;
}
var Rr = (e) => (wr << BigInt(e)) - wr;
function zr(e, t, n) {
	if (typeof e != "number" || e < 2) throw Error("hashLen must be a number");
	if (typeof t != "number" || t < 2) throw Error("qByteLen must be a number");
	if (typeof n != "function") throw Error("hmacFn must be a function");
	let r = (e) => new Uint8Array(e), i = (e) => Uint8Array.of(e), a = r(e), o = r(e), s = 0, c = () => {
		a.fill(1), o.fill(0), s = 0;
	}, l = (...e) => n(o, a, ...e), u = (e = r(0)) => {
		o = l(i(0), e), a = l(), e.length !== 0 && (o = l(i(1), e), a = l());
	}, d = () => {
		if (s++ >= 1e3) throw Error("drbg: tried 1000 values");
		let e = 0, n = [];
		for (; e < t;) {
			a = l();
			let t = a.slice();
			n.push(t), e += a.length;
		}
		return ce(...n);
	};
	return (e, t) => {
		c(), u(e);
		let n;
		for (; !(n = t(d()));) u();
		return c(), n;
	};
}
function Br(e) {
	return typeof e == "function" && Number.isSafeInteger(e.outputLen);
}
function Vr(e, t, n = {}) {
	if (!e || typeof e != "object") throw Error("expected valid options object");
	function r(t, n, r) {
		let i = e[t];
		if (r && i === void 0) return;
		let a = typeof i;
		if (a !== n || i === null) throw Error(`param "${t}" is invalid: expected ${n}, got ${a}`);
	}
	Object.entries(t).forEach(([e, t]) => r(e, t, !1)), Object.entries(n).forEach(([e, t]) => r(e, t, !0));
}
function Hr(e) {
	let t = /* @__PURE__ */ new WeakMap();
	return (n, ...r) => {
		let i = t.get(n);
		if (i !== void 0) return i;
		let a = e(n, ...r);
		return t.set(n, a), a;
	};
}
//#endregion
//#region node_modules/@noble/curves/esm/abstract/modular.js
var Ur = BigInt(0), Wr = BigInt(1), Gr = /* @__PURE__ */ BigInt(2), Kr = /* @__PURE__ */ BigInt(3), qr = /* @__PURE__ */ BigInt(4), Jr = /* @__PURE__ */ BigInt(5), Yr = /* @__PURE__ */ BigInt(7), Xr = /* @__PURE__ */ BigInt(8), Zr = /* @__PURE__ */ BigInt(9), Qr = /* @__PURE__ */ BigInt(16);
function $r(e, t) {
	let n = e % t;
	return n >= Ur ? n : t + n;
}
function ei(e, t, n) {
	let r = e;
	for (; t-- > Ur;) r *= r, r %= n;
	return r;
}
function ti(e, t) {
	if (e === Ur) throw Error("invert: expected non-zero number");
	if (t <= Ur) throw Error("invert: expected positive modulus, got " + t);
	let n = $r(e, t), r = t, i = Ur, a = Wr, o = Wr, s = Ur;
	for (; n !== Ur;) {
		let e = r / n, t = r % n, c = i - o * e, l = a - s * e;
		r = n, n = t, i = o, a = s, o = c, s = l;
	}
	if (r !== Wr) throw Error("invert: does not exist");
	return $r(i, t);
}
function ni(e, t, n) {
	if (!e.eql(e.sqr(t), n)) throw Error("Cannot find square root");
}
function ri(e, t) {
	let n = (e.ORDER + Wr) / qr, r = e.pow(t, n);
	return ni(e, r, t), r;
}
function ii(e, t) {
	let n = (e.ORDER - Jr) / Xr, r = e.mul(t, Gr), i = e.pow(r, n), a = e.mul(t, i), o = e.mul(e.mul(a, Gr), i), s = e.mul(a, e.sub(o, e.ONE));
	return ni(e, s, t), s;
}
function ai(e) {
	let t = mi(e), n = oi(e), r = n(t, t.neg(t.ONE)), i = n(t, r), a = n(t, t.neg(r)), o = (e + Yr) / Qr;
	return (e, t) => {
		let n = e.pow(t, o), s = e.mul(n, r), c = e.mul(n, i), l = e.mul(n, a), u = e.eql(e.sqr(s), t), d = e.eql(e.sqr(c), t);
		n = e.cmov(n, s, u), s = e.cmov(l, c, d);
		let f = e.eql(e.sqr(s), t), p = e.cmov(n, s, f);
		return ni(e, p, t), p;
	};
}
function oi(e) {
	if (e < Kr) throw Error("sqrt is not defined for small field");
	let t = e - Wr, n = 0;
	for (; t % Gr === Ur;) t /= Gr, n++;
	let r = Gr, i = mi(e);
	for (; fi(i, r) === 1;) if (r++ > 1e3) throw Error("Cannot find square root: probably non-prime P");
	if (n === 1) return ri;
	let a = i.pow(r, t), o = (t + Wr) / Gr;
	return function(e, r) {
		if (e.is0(r)) return r;
		if (fi(e, r) !== 1) throw Error("Cannot find square root");
		let i = n, s = e.mul(e.ONE, a), c = e.pow(r, t), l = e.pow(r, o);
		for (; !e.eql(c, e.ONE);) {
			if (e.is0(c)) return e.ZERO;
			let t = 1, n = e.sqr(c);
			for (; !e.eql(n, e.ONE);) if (t++, n = e.sqr(n), t === i) throw Error("Cannot find square root");
			let r = Wr << BigInt(i - t - 1), a = e.pow(s, r);
			i = t, s = e.sqr(a), c = e.mul(c, s), l = e.mul(l, a);
		}
		return l;
	};
}
function si(e) {
	return e % qr === Kr ? ri : e % Xr === Jr ? ii : e % Qr === Zr ? ai(e) : oi(e);
}
var ci = [
	"create",
	"isValid",
	"is0",
	"neg",
	"inv",
	"sqrt",
	"sqr",
	"eql",
	"add",
	"sub",
	"mul",
	"pow",
	"div",
	"addN",
	"subN",
	"mulN",
	"sqrN"
];
function li(e) {
	return Vr(e, ci.reduce((e, t) => (e[t] = "function", e), {
		ORDER: "bigint",
		MASK: "bigint",
		BYTES: "number",
		BITS: "number"
	})), e;
}
function ui(e, t, n) {
	if (n < Ur) throw Error("invalid exponent, negatives unsupported");
	if (n === Ur) return e.ONE;
	if (n === Wr) return t;
	let r = e.ONE, i = t;
	for (; n > Ur;) n & Wr && (r = e.mul(r, i)), i = e.sqr(i), n >>= Wr;
	return r;
}
function di(e, t, n = !1) {
	let r = Array(t.length).fill(n ? e.ZERO : void 0), i = t.reduce((t, n, i) => e.is0(n) ? t : (r[i] = t, e.mul(t, n)), e.ONE), a = e.inv(i);
	return t.reduceRight((t, n, i) => e.is0(n) ? t : (r[i] = e.mul(t, r[i]), e.mul(t, n)), a), r;
}
function fi(e, t) {
	let n = (e.ORDER - Wr) / Gr, r = e.pow(t, n), i = e.eql(r, e.ONE), a = e.eql(r, e.ZERO), o = e.eql(r, e.neg(e.ONE));
	if (!i && !a && !o) throw Error("invalid Legendre symbol result");
	return i ? 1 : a ? 0 : -1;
}
function pi(e, t) {
	t !== void 0 && C(t);
	let n = t === void 0 ? e.toString(2).length : t;
	return {
		nBitLength: n,
		nByteLength: Math.ceil(n / 8)
	};
}
function mi(e, t, n = !1, r = {}) {
	if (e <= Ur) throw Error("invalid field: expected ORDER > 0, got " + e);
	let i, a, o = !1, s;
	if (typeof t == "object" && t) {
		if (r.sqrt || n) throw Error("cannot specify opts in two arguments");
		let e = t;
		e.BITS && (i = e.BITS), e.sqrt && (a = e.sqrt), typeof e.isLE == "boolean" && (n = e.isLE), typeof e.modFromBytes == "boolean" && (o = e.modFromBytes), s = e.allowedLengths;
	} else typeof t == "number" && (i = t), r.sqrt && (a = r.sqrt);
	let { nBitLength: c, nByteLength: l } = pi(e, i);
	if (l > 2048) throw Error("invalid field: expected ORDER of <= 2048 bytes");
	let u, d = Object.freeze({
		ORDER: e,
		isLE: n,
		BITS: c,
		BYTES: l,
		MASK: Rr(c),
		ZERO: Ur,
		ONE: Wr,
		allowedLengths: s,
		create: (t) => $r(t, e),
		isValid: (t) => {
			if (typeof t != "bigint") throw Error("invalid field element: expected bigint, got " + typeof t);
			return Ur <= t && t < e;
		},
		is0: (e) => e === Ur,
		isValidNot0: (e) => !d.is0(e) && d.isValid(e),
		isOdd: (e) => (e & Wr) === Wr,
		neg: (t) => $r(-t, e),
		eql: (e, t) => e === t,
		sqr: (t) => $r(t * t, e),
		add: (t, n) => $r(t + n, e),
		sub: (t, n) => $r(t - n, e),
		mul: (t, n) => $r(t * n, e),
		pow: (e, t) => ui(d, e, t),
		div: (t, n) => $r(t * ti(n, e), e),
		sqrN: (e) => e * e,
		addN: (e, t) => e + t,
		subN: (e, t) => e - t,
		mulN: (e, t) => e * t,
		inv: (t) => ti(t, e),
		sqrt: a || ((t) => (u ||= si(e), u(d, t))),
		toBytes: (e) => n ? Mr(e, l) : jr(e, l),
		fromBytes: (t, r = !0) => {
			if (s) {
				if (!s.includes(t.length) || t.length > l) throw Error("Field.fromBytes: expected " + s + " bytes, got " + t.length);
				let e = new Uint8Array(l);
				e.set(t, n ? 0 : e.length - t.length), t = e;
			}
			if (t.length !== l) throw Error("Field.fromBytes: expected " + l + " bytes, got " + t.length);
			let i = n ? Ar(t) : kr(t);
			if (o && (i = $r(i, e)), !r && !d.isValid(i)) throw Error("invalid field element: outside of range 0..ORDER");
			return i;
		},
		invertBatch: (e) => di(d, e),
		cmov: (e, t, n) => n ? t : e
	});
	return Object.freeze(d);
}
function hi(e) {
	if (typeof e != "bigint") throw Error("field order must be bigint");
	let t = e.toString(2).length;
	return Math.ceil(t / 8);
}
function gi(e) {
	let t = hi(e);
	return t + Math.ceil(t / 2);
}
function _i(e, t, n = !1) {
	let r = e.length, i = hi(t), a = gi(t);
	if (r < 16 || r < a || r > 1024) throw Error("expected " + a + "-1024 bytes of input, got " + r);
	let o = $r(n ? Ar(e) : kr(e), t - Wr) + Wr;
	return n ? Mr(o, i) : jr(o, i);
}
//#endregion
//#region node_modules/@noble/curves/esm/abstract/curve.js
var vi = BigInt(0), yi = BigInt(1);
function bi(e, t) {
	let n = t.negate();
	return e ? n : t;
}
function xi(e, t) {
	let n = di(e.Fp, t.map((e) => e.Z));
	return t.map((t, r) => e.fromAffine(t.toAffine(n[r])));
}
function Si(e, t) {
	if (!Number.isSafeInteger(e) || e <= 0 || e > t) throw Error("invalid window size, expected [1.." + t + "], got W=" + e);
}
function Ci(e, t) {
	Si(e, t);
	let n = Math.ceil(t / e) + 1, r = 2 ** (e - 1), i = 2 ** e;
	return {
		windows: n,
		windowSize: r,
		mask: Rr(e),
		maxNumber: i,
		shiftBy: BigInt(e)
	};
}
function wi(e, t, n) {
	let { windowSize: r, mask: i, maxNumber: a, shiftBy: o } = n, s = Number(e & i), c = e >> o;
	s > r && (s -= a, c += yi);
	let l = t * r, u = l + Math.abs(s) - 1, d = s === 0, f = s < 0, p = t % 2 != 0;
	return {
		nextN: c,
		offset: u,
		isZero: d,
		isNeg: f,
		isNegF: p,
		offsetF: l
	};
}
function Ti(e, t) {
	if (!Array.isArray(e)) throw Error("array expected");
	e.forEach((e, n) => {
		if (!(e instanceof t)) throw Error("invalid point at index " + n);
	});
}
function Ei(e, t) {
	if (!Array.isArray(e)) throw Error("array of scalars expected");
	e.forEach((e, n) => {
		if (!t.isValid(e)) throw Error("invalid scalar at index " + n);
	});
}
var Di = /* @__PURE__ */ new WeakMap(), Oi = /* @__PURE__ */ new WeakMap();
function ki(e) {
	return Oi.get(e) || 1;
}
function Ai(e) {
	if (e !== vi) throw Error("invalid wNAF");
}
var ji = class {
	constructor(e, t) {
		this.BASE = e.BASE, this.ZERO = e.ZERO, this.Fn = e.Fn, this.bits = t;
	}
	_unsafeLadder(e, t, n = this.ZERO) {
		let r = e;
		for (; t > vi;) t & yi && (n = n.add(r)), r = r.double(), t >>= yi;
		return n;
	}
	precomputeWindow(e, t) {
		let { windows: n, windowSize: r } = Ci(t, this.bits), i = [], a = e, o = a;
		for (let e = 0; e < n; e++) {
			o = a, i.push(o);
			for (let e = 1; e < r; e++) o = o.add(a), i.push(o);
			a = o.double();
		}
		return i;
	}
	wNAF(e, t, n) {
		if (!this.Fn.isValid(n)) throw Error("invalid scalar");
		let r = this.ZERO, i = this.BASE, a = Ci(e, this.bits);
		for (let e = 0; e < a.windows; e++) {
			let { nextN: o, offset: s, isZero: c, isNeg: l, isNegF: u, offsetF: d } = wi(n, e, a);
			n = o, c ? i = i.add(bi(u, t[d])) : r = r.add(bi(l, t[s]));
		}
		return Ai(n), {
			p: r,
			f: i
		};
	}
	wNAFUnsafe(e, t, n, r = this.ZERO) {
		let i = Ci(e, this.bits);
		for (let e = 0; e < i.windows && n !== vi; e++) {
			let { nextN: a, offset: o, isZero: s, isNeg: c } = wi(n, e, i);
			if (n = a, !s) {
				let e = t[o];
				r = r.add(c ? e.negate() : e);
			}
		}
		return Ai(n), r;
	}
	getPrecomputes(e, t, n) {
		let r = Di.get(t);
		return r || (r = this.precomputeWindow(t, e), e !== 1 && (typeof n == "function" && (r = n(r)), Di.set(t, r))), r;
	}
	cached(e, t, n) {
		let r = ki(e);
		return this.wNAF(r, this.getPrecomputes(r, e, n), t);
	}
	unsafe(e, t, n, r) {
		let i = ki(e);
		return i === 1 ? this._unsafeLadder(e, t, r) : this.wNAFUnsafe(i, this.getPrecomputes(i, e, n), t, r);
	}
	createCache(e, t) {
		Si(t, this.bits), Oi.set(e, t), Di.delete(e);
	}
	hasCache(e) {
		return ki(e) !== 1;
	}
};
function Mi(e, t, n, r) {
	let i = t, a = e.ZERO, o = e.ZERO;
	for (; n > vi || r > vi;) n & yi && (a = a.add(i)), r & yi && (o = o.add(i)), i = i.double(), n >>= yi, r >>= yi;
	return {
		p1: a,
		p2: o
	};
}
function Ni(e, t, n, r) {
	Ti(n, e), Ei(r, t);
	let i = n.length, a = r.length;
	if (i !== a) throw Error("arrays of points and scalars must have equal length");
	let o = e.ZERO, s = Lr(BigInt(i)), c = 1;
	s > 12 ? c = s - 3 : s > 4 ? c = s - 2 : s > 0 && (c = 2);
	let l = Rr(c), u = Array(Number(l) + 1).fill(o), d = Math.floor((t.BITS - 1) / c) * c, f = o;
	for (let e = d; e >= 0; e -= c) {
		u.fill(o);
		for (let t = 0; t < a; t++) {
			let i = r[t], a = Number(i >> BigInt(e) & l);
			u[a] = u[a].add(n[t]);
		}
		let t = o;
		for (let e = u.length - 1, n = o; e > 0; e--) n = n.add(u[e]), t = t.add(n);
		if (f = f.add(t), e !== 0) for (let e = 0; e < c; e++) f = f.double();
	}
	return f;
}
function Pi(e, t, n) {
	if (t) {
		if (t.ORDER !== e) throw Error("Field.ORDER must match order: Fp == p, Fn == n");
		return li(t), t;
	} else return mi(e, { isLE: n });
}
function Fi(e, t, n = {}, r) {
	if (r === void 0 && (r = e === "edwards"), !t || typeof t != "object") throw Error(`expected valid ${e} CURVE object`);
	for (let e of [
		"p",
		"n",
		"h"
	]) {
		let n = t[e];
		if (!(typeof n == "bigint" && n > vi)) throw Error(`CURVE.${e} must be positive bigint`);
	}
	let i = Pi(t.p, n.Fp, r), a = Pi(t.n, n.Fn, r), o = [
		"Gx",
		"Gy",
		"a",
		e === "weierstrass" ? "b" : "d"
	];
	for (let e of o) if (!i.isValid(t[e])) throw Error(`CURVE.${e} must be valid field element of CURVE.Fp`);
	return t = Object.freeze(Object.assign({}, t)), {
		CURVE: t,
		Fp: i,
		Fn: a
	};
}
//#endregion
//#region node_modules/@noble/curves/esm/abstract/weierstrass.js
var Ii = (e, t) => (e + (e >= 0 ? t : -t) / Ui) / t;
function Li(e, t, n) {
	let [[r, i], [a, o]] = t, s = Ii(o * e, n), c = Ii(-i * e, n), l = e - s * r - c * a, u = -s * i - c * o, d = l < Vi, f = u < Vi;
	d && (l = -l), f && (u = -u);
	let p = Rr(Math.ceil(Lr(n) / 2)) + Hi;
	if (l < Vi || l >= p || u < Vi || u >= p) throw Error("splitScalar (endomorphism): failed, k=" + e);
	return {
		k1neg: d,
		k1: l,
		k2neg: f,
		k2: u
	};
}
function Ri(e) {
	if (![
		"compact",
		"recovered",
		"der"
	].includes(e)) throw Error("Signature format must be \"compact\", \"recovered\", or \"der\"");
	return e;
}
function zi(e, t) {
	let n = {};
	for (let r of Object.keys(t)) n[r] = e[r] === void 0 ? t[r] : e[r];
	return Tr(n.lowS, "lowS"), Tr(n.prehash, "prehash"), n.format !== void 0 && Ri(n.format), n;
}
var Bi = {
	Err: class extends Error {
		constructor(e = "") {
			super(e);
		}
	},
	_tlv: {
		encode: (e, t) => {
			let { Err: n } = Bi;
			if (e < 0 || e > 256) throw new n("tlv.encode: wrong tag");
			if (t.length & 1) throw new n("tlv.encode: unpadded data");
			let r = t.length / 2, i = Dr(r);
			if (i.length / 2 & 128) throw new n("tlv.encode: long form length too big");
			let a = r > 127 ? Dr(i.length / 2 | 128) : "";
			return Dr(e) + a + i + t;
		},
		decode(e, t) {
			let { Err: n } = Bi, r = 0;
			if (e < 0 || e > 256) throw new n("tlv.encode: wrong tag");
			if (t.length < 2 || t[r++] !== e) throw new n("tlv.decode: wrong tlv");
			let i = t[r++], a = !!(i & 128), o = 0;
			if (!a) o = i;
			else {
				let e = i & 127;
				if (!e) throw new n("tlv.decode(long): indefinite length not supported");
				if (e > 4) throw new n("tlv.decode(long): byte length is too big");
				let a = t.subarray(r, r + e);
				if (a.length !== e) throw new n("tlv.decode: length bytes not complete");
				if (a[0] === 0) throw new n("tlv.decode(long): zero leftmost byte");
				for (let e of a) o = o << 8 | e;
				if (r += e, o < 128) throw new n("tlv.decode(long): not minimal encoding");
			}
			let s = t.subarray(r, r + o);
			if (s.length !== o) throw new n("tlv.decode: wrong value length");
			return {
				v: s,
				l: t.subarray(r + o)
			};
		}
	},
	_int: {
		encode(e) {
			let { Err: t } = Bi;
			if (e < Vi) throw new t("integer: negative integers are not allowed");
			let n = Dr(e);
			if (Number.parseInt(n[0], 16) & 8 && (n = "00" + n), n.length & 1) throw new t("unexpected DER parsing assertion: unpadded hex");
			return n;
		},
		decode(e) {
			let { Err: t } = Bi;
			if (e[0] & 128) throw new t("invalid signature integer: negative");
			if (e[0] === 0 && !(e[1] & 128)) throw new t("invalid signature integer: unnecessary leading zero");
			return kr(e);
		}
	},
	toSig(e) {
		let { Err: t, _int: n, _tlv: r } = Bi, i = Nr("signature", e), { v: a, l: o } = r.decode(48, i);
		if (o.length) throw new t("invalid signature: left bytes after parsing");
		let { v: s, l: c } = r.decode(2, a), { v: l, l: u } = r.decode(2, c);
		if (u.length) throw new t("invalid signature: left bytes after parsing");
		return {
			r: n.decode(s),
			s: n.decode(l)
		};
	},
	hexFromSig(e) {
		let { _tlv: t, _int: n } = Bi, r = t.encode(2, n.encode(e.r)) + t.encode(2, n.encode(e.s));
		return t.encode(48, r);
	}
}, Vi = BigInt(0), Hi = BigInt(1), Ui = BigInt(2), Wi = BigInt(3), Gi = BigInt(4);
function Ki(e, t) {
	let { BYTES: n } = e, r;
	if (typeof t == "bigint") r = t;
	else {
		let i = Nr("private key", t);
		try {
			r = e.fromBytes(i);
		} catch {
			throw Error(`invalid private key: expected ui8a of size ${n}, got ${typeof t}`);
		}
	}
	if (!e.isValidNot0(r)) throw Error("invalid private key: out of range [1..N-1]");
	return r;
}
function qi(e, t = {}) {
	let n = Fi("weierstrass", e, t), { Fp: r, Fn: i } = n, a = n.CURVE, { h: o, n: s } = a;
	Vr(t, {}, {
		allowInfinityPoint: "boolean",
		clearCofactor: "function",
		isTorsionFree: "function",
		fromBytes: "function",
		toBytes: "function",
		endo: "object",
		wrapPrivateKey: "boolean"
	});
	let { endo: c } = t;
	if (c && (!r.is0(a.a) || typeof c.beta != "bigint" || !Array.isArray(c.basises))) throw Error("invalid endo: expected \"beta\": bigint and \"basises\": array");
	let l = Zi(r, i);
	function u() {
		if (!r.isOdd) throw Error("compression is not supported: Field does not have .isOdd()");
	}
	function d(e, t, n) {
		let { x: i, y: a } = t.toAffine(), o = r.toBytes(i);
		return Tr(n, "isCompressed"), n ? (u(), ce(Ji(!r.isOdd(a)), o)) : ce(Uint8Array.of(4), o, r.toBytes(a));
	}
	function f(e) {
		Er(e, void 0, "Point");
		let { publicKey: t, publicKeyUncompressed: n } = l, i = e.length, a = e[0], o = e.subarray(1);
		if (i === t && (a === 2 || a === 3)) {
			let e = r.fromBytes(o);
			if (!r.isValid(e)) throw Error("bad point: is not on curve, wrong x");
			let t = h(e), n;
			try {
				n = r.sqrt(t);
			} catch (e) {
				let t = e instanceof Error ? ": " + e.message : "";
				throw Error("bad point: is not on curve, sqrt error" + t);
			}
			u();
			let i = r.isOdd(n);
			return (a & 1) == 1 !== i && (n = r.neg(n)), {
				x: e,
				y: n
			};
		} else if (i === n && a === 4) {
			let e = r.BYTES, t = r.fromBytes(o.subarray(0, e)), n = r.fromBytes(o.subarray(e, e * 2));
			if (!g(t, n)) throw Error("bad point: is not on curve");
			return {
				x: t,
				y: n
			};
		} else throw Error(`bad point: got length ${i}, expected compressed=${t} or uncompressed=${n}`);
	}
	let p = t.toBytes || d, m = t.fromBytes || f;
	function h(e) {
		let t = r.sqr(e), n = r.mul(t, e);
		return r.add(r.add(n, r.mul(e, a.a)), a.b);
	}
	function g(e, t) {
		let n = r.sqr(t), i = h(e);
		return r.eql(n, i);
	}
	if (!g(a.Gx, a.Gy)) throw Error("bad curve params: generator point");
	let _ = r.mul(r.pow(a.a, Wi), Gi), v = r.mul(r.sqr(a.b), BigInt(27));
	if (r.is0(r.add(_, v))) throw Error("bad curve params: a or b");
	function y(e, t, n = !1) {
		if (!r.isValid(t) || n && r.is0(t)) throw Error(`bad point coordinate ${e}`);
		return t;
	}
	function b(e) {
		if (!(e instanceof T)) throw Error("ProjectivePoint expected");
	}
	function x(e) {
		if (!c || !c.basises) throw Error("no endo");
		return Li(e, c.basises, i.ORDER);
	}
	let S = Hr((e, t) => {
		let { X: n, Y: i, Z: a } = e;
		if (r.eql(a, r.ONE)) return {
			x: n,
			y: i
		};
		let o = e.is0();
		t ??= o ? r.ONE : r.inv(a);
		let s = r.mul(n, t), c = r.mul(i, t), l = r.mul(a, t);
		if (o) return {
			x: r.ZERO,
			y: r.ZERO
		};
		if (!r.eql(l, r.ONE)) throw Error("invZ was invalid");
		return {
			x: s,
			y: c
		};
	}), C = Hr((e) => {
		if (e.is0()) {
			if (t.allowInfinityPoint && !r.is0(e.Y)) return;
			throw Error("bad point: ZERO");
		}
		let { x: n, y: i } = e.toAffine();
		if (!r.isValid(n) || !r.isValid(i)) throw Error("bad point: x or y not field elements");
		if (!g(n, i)) throw Error("bad point: equation left != right");
		if (!e.isTorsionFree()) throw Error("bad point: not in prime-order subgroup");
		return !0;
	});
	function w(e, t, n, i, a) {
		return n = new T(r.mul(n.X, e), n.Y, n.Z), t = bi(i, t), n = bi(a, n), t.add(n);
	}
	class T {
		constructor(e, t, n) {
			this.X = y("x", e), this.Y = y("y", t, !0), this.Z = y("z", n), Object.freeze(this);
		}
		static CURVE() {
			return a;
		}
		static fromAffine(e) {
			let { x: t, y: n } = e || {};
			if (!e || !r.isValid(t) || !r.isValid(n)) throw Error("invalid affine point");
			if (e instanceof T) throw Error("projective point not allowed");
			return r.is0(t) && r.is0(n) ? T.ZERO : new T(t, n, r.ONE);
		}
		static fromBytes(e) {
			let t = T.fromAffine(m(Er(e, void 0, "point")));
			return t.assertValidity(), t;
		}
		static fromHex(e) {
			return T.fromBytes(Nr("pointHex", e));
		}
		get x() {
			return this.toAffine().x;
		}
		get y() {
			return this.toAffine().y;
		}
		precompute(e = 8, t = !0) {
			return D.createCache(this, e), t || this.multiply(Wi), this;
		}
		assertValidity() {
			C(this);
		}
		hasEvenY() {
			let { y: e } = this.toAffine();
			if (!r.isOdd) throw Error("Field doesn't support isOdd");
			return !r.isOdd(e);
		}
		equals(e) {
			b(e);
			let { X: t, Y: n, Z: i } = this, { X: a, Y: o, Z: s } = e, c = r.eql(r.mul(t, s), r.mul(a, i)), l = r.eql(r.mul(n, s), r.mul(o, i));
			return c && l;
		}
		negate() {
			return new T(this.X, r.neg(this.Y), this.Z);
		}
		double() {
			let { a: e, b: t } = a, n = r.mul(t, Wi), { X: i, Y: o, Z: s } = this, c = r.ZERO, l = r.ZERO, u = r.ZERO, d = r.mul(i, i), f = r.mul(o, o), p = r.mul(s, s), m = r.mul(i, o);
			return m = r.add(m, m), u = r.mul(i, s), u = r.add(u, u), c = r.mul(e, u), l = r.mul(n, p), l = r.add(c, l), c = r.sub(f, l), l = r.add(f, l), l = r.mul(c, l), c = r.mul(m, c), u = r.mul(n, u), p = r.mul(e, p), m = r.sub(d, p), m = r.mul(e, m), m = r.add(m, u), u = r.add(d, d), d = r.add(u, d), d = r.add(d, p), d = r.mul(d, m), l = r.add(l, d), p = r.mul(o, s), p = r.add(p, p), d = r.mul(p, m), c = r.sub(c, d), u = r.mul(p, f), u = r.add(u, u), u = r.add(u, u), new T(c, l, u);
		}
		add(e) {
			b(e);
			let { X: t, Y: n, Z: i } = this, { X: o, Y: s, Z: c } = e, l = r.ZERO, u = r.ZERO, d = r.ZERO, f = a.a, p = r.mul(a.b, Wi), m = r.mul(t, o), h = r.mul(n, s), g = r.mul(i, c), _ = r.add(t, n), v = r.add(o, s);
			_ = r.mul(_, v), v = r.add(m, h), _ = r.sub(_, v), v = r.add(t, i);
			let y = r.add(o, c);
			return v = r.mul(v, y), y = r.add(m, g), v = r.sub(v, y), y = r.add(n, i), l = r.add(s, c), y = r.mul(y, l), l = r.add(h, g), y = r.sub(y, l), d = r.mul(f, v), l = r.mul(p, g), d = r.add(l, d), l = r.sub(h, d), d = r.add(h, d), u = r.mul(l, d), h = r.add(m, m), h = r.add(h, m), g = r.mul(f, g), v = r.mul(p, v), h = r.add(h, g), g = r.sub(m, g), g = r.mul(f, g), v = r.add(v, g), m = r.mul(h, v), u = r.add(u, m), m = r.mul(y, v), l = r.mul(_, l), l = r.sub(l, m), m = r.mul(_, h), d = r.mul(y, d), d = r.add(d, m), new T(l, u, d);
		}
		subtract(e) {
			return this.add(e.negate());
		}
		is0() {
			return this.equals(T.ZERO);
		}
		multiply(e) {
			let { endo: n } = t;
			if (!i.isValidNot0(e)) throw Error("invalid scalar: out of range");
			let r, a, o = (e) => D.cached(this, e, (e) => xi(T, e));
			if (n) {
				let { k1neg: t, k1: i, k2neg: s, k2: c } = x(e), { p: l, f: u } = o(i), { p: d, f } = o(c);
				a = u.add(f), r = w(n.beta, l, d, t, s);
			} else {
				let { p: t, f: n } = o(e);
				r = t, a = n;
			}
			return xi(T, [r, a])[0];
		}
		multiplyUnsafe(e) {
			let { endo: n } = t, r = this;
			if (!i.isValid(e)) throw Error("invalid scalar: out of range");
			if (e === Vi || r.is0()) return T.ZERO;
			if (e === Hi) return r;
			if (D.hasCache(this)) return this.multiply(e);
			if (n) {
				let { k1neg: t, k1: i, k2neg: a, k2: o } = x(e), { p1: s, p2: c } = Mi(T, r, i, o);
				return w(n.beta, s, c, t, a);
			} else return D.unsafe(r, e);
		}
		multiplyAndAddUnsafe(e, t, n) {
			let r = this.multiplyUnsafe(t).add(e.multiplyUnsafe(n));
			return r.is0() ? void 0 : r;
		}
		toAffine(e) {
			return S(this, e);
		}
		isTorsionFree() {
			let { isTorsionFree: e } = t;
			return o === Hi ? !0 : e ? e(T, this) : D.unsafe(this, s).is0();
		}
		clearCofactor() {
			let { clearCofactor: e } = t;
			return o === Hi ? this : e ? e(T, this) : this.multiplyUnsafe(o);
		}
		isSmallOrder() {
			return this.multiplyUnsafe(o).is0();
		}
		toBytes(e = !0) {
			return Tr(e, "isCompressed"), this.assertValidity(), p(T, this, e);
		}
		toHex(e = !0) {
			return ae(this.toBytes(e));
		}
		toString() {
			return `<Point ${this.is0() ? "ZERO" : this.toHex()}>`;
		}
		get px() {
			return this.X;
		}
		get py() {
			return this.X;
		}
		get pz() {
			return this.Z;
		}
		toRawBytes(e = !0) {
			return this.toBytes(e);
		}
		_setWindowSize(e) {
			this.precompute(e);
		}
		static normalizeZ(e) {
			return xi(T, e);
		}
		static msm(e, t) {
			return Ni(T, i, e, t);
		}
		static fromPrivateKey(e) {
			return T.BASE.multiply(Ki(i, e));
		}
	}
	T.BASE = new T(a.Gx, a.Gy, r.ONE), T.ZERO = new T(r.ZERO, r.ONE, r.ZERO), T.Fp = r, T.Fn = i;
	let E = i.BITS, D = new ji(T, t.endo ? Math.ceil(E / 2) : E);
	return T.BASE.precompute(8), T;
}
function Ji(e) {
	return Uint8Array.of(e ? 2 : 3);
}
function Yi(e, t) {
	let n = e.ORDER, r = Vi;
	for (let e = n - Hi; e % Ui === Vi; e /= Ui) r += Hi;
	let i = r, a = Ui << i - Hi - Hi, o = a * Ui, s = (n - Hi) / o, c = (s - Hi) / Ui, l = o - Hi, u = a, d = e.pow(t, s), f = e.pow(t, (s + Hi) / Ui), p = (t, n) => {
		let r = d, a = e.pow(n, l), o = e.sqr(a);
		o = e.mul(o, n);
		let s = e.mul(t, o);
		s = e.pow(s, c), s = e.mul(s, a), a = e.mul(s, n), o = e.mul(s, t);
		let p = e.mul(o, a);
		s = e.pow(p, u);
		let m = e.eql(s, e.ONE);
		a = e.mul(o, f), s = e.mul(p, r), o = e.cmov(a, o, m), p = e.cmov(s, p, m);
		for (let t = i; t > Hi; t--) {
			let n = t - Ui;
			n = Ui << n - Hi;
			let i = e.pow(p, n), s = e.eql(i, e.ONE);
			a = e.mul(o, r), r = e.mul(r, r), i = e.mul(p, r), o = e.cmov(a, o, s), p = e.cmov(i, p, s);
		}
		return {
			isValid: m,
			value: o
		};
	};
	if (e.ORDER % Gi === Wi) {
		let n = (e.ORDER - Wi) / Gi, r = e.sqrt(e.neg(t));
		p = (t, i) => {
			let a = e.sqr(i), o = e.mul(t, i);
			a = e.mul(a, o);
			let s = e.pow(a, n);
			s = e.mul(s, o);
			let c = e.mul(s, r), l = e.mul(e.sqr(s), i), u = e.eql(l, t);
			return {
				isValid: u,
				value: e.cmov(c, s, u)
			};
		};
	}
	return p;
}
function Xi(e, t) {
	li(e);
	let { A: n, B: r, Z: i } = t;
	if (!e.isValid(n) || !e.isValid(r) || !e.isValid(i)) throw Error("mapToCurveSimpleSWU: invalid opts");
	let a = Yi(e, i);
	if (!e.isOdd) throw Error("Field does not have .isOdd()");
	return (t) => {
		let o, s, c, l, u, d, f, p;
		o = e.sqr(t), o = e.mul(o, i), s = e.sqr(o), s = e.add(s, o), c = e.add(s, e.ONE), c = e.mul(c, r), l = e.cmov(i, e.neg(s), !e.eql(s, e.ZERO)), l = e.mul(l, n), s = e.sqr(c), d = e.sqr(l), u = e.mul(d, n), s = e.add(s, u), s = e.mul(s, c), d = e.mul(d, l), u = e.mul(d, r), s = e.add(s, u), f = e.mul(o, c);
		let { isValid: m, value: h } = a(s, d);
		p = e.mul(o, t), p = e.mul(p, h), f = e.cmov(f, c, m), p = e.cmov(p, h, m);
		let g = e.isOdd(t) === e.isOdd(p);
		p = e.cmov(e.neg(p), p, g);
		let _ = di(e, [l], !0)[0];
		return f = e.mul(f, _), {
			x: f,
			y: p
		};
	};
}
function Zi(e, t) {
	return {
		secretKey: t.BYTES,
		publicKey: 1 + e.BYTES,
		publicKeyUncompressed: 1 + 2 * e.BYTES,
		publicKeyHasPrefix: !0,
		signature: 2 * t.BYTES
	};
}
function Qi(e, t = {}) {
	let { Fn: n } = e, r = t.randomBytes || z, i = Object.assign(Zi(e.Fp, n), { seed: gi(n.ORDER) });
	function a(e) {
		try {
			return !!Ki(n, e);
		} catch {
			return !1;
		}
	}
	function o(t, n) {
		let { publicKey: r, publicKeyUncompressed: a } = i;
		try {
			let i = t.length;
			return n === !0 && i !== r || n === !1 && i !== a ? !1 : !!e.fromBytes(t);
		} catch {
			return !1;
		}
	}
	function s(e = r(i.seed)) {
		return _i(Er(e, i.seed, "seed"), n.ORDER);
	}
	function c(t, r = !0) {
		return e.BASE.multiply(Ki(n, t)).toBytes(r);
	}
	function l(e) {
		let t = s(e);
		return {
			secretKey: t,
			publicKey: c(t)
		};
	}
	function u(t) {
		if (typeof t == "bigint") return !1;
		if (t instanceof e) return !0;
		let { secretKey: r, publicKey: a, publicKeyUncompressed: o } = i;
		if (n.allowedLengths || r === a) return;
		let s = Nr("key", t).length;
		return s === a || s === o;
	}
	function d(t, r, i = !0) {
		if (u(t) === !0) throw Error("first arg must be private key");
		if (u(r) === !1) throw Error("second arg must be public key");
		let a = Ki(n, t);
		return e.fromHex(r).multiply(a).toBytes(i);
	}
	return Object.freeze({
		getPublicKey: c,
		getSharedSecret: d,
		keygen: l,
		Point: e,
		utils: {
			isValidSecretKey: a,
			isValidPublicKey: o,
			randomSecretKey: s,
			isValidPrivateKey: a,
			randomPrivateKey: s,
			normPrivateKeyToScalar: (e) => Ki(n, e),
			precompute(t = 8, n = e.BASE) {
				return n.precompute(t, !1);
			}
		},
		lengths: i
	});
}
function $i(e, t, n = {}) {
	T(t), Vr(n, {}, {
		hmac: "function",
		lowS: "boolean",
		randomBytes: "function",
		bits2int: "function",
		bits2int_modN: "function"
	});
	let r = n.randomBytes || z, i = n.hmac || ((e, ...n) => _r(t, e, ce(...n))), { Fp: a, Fn: o } = e, { ORDER: s, BITS: c } = o, { keygen: l, getPublicKey: u, getSharedSecret: d, utils: f, lengths: p } = Qi(e, n), m = {
		prehash: !1,
		lowS: typeof n.lowS == "boolean" ? n.lowS : !1,
		format: void 0,
		extraEntropy: !1
	}, h = "compact";
	function g(e) {
		return e > s >> Hi;
	}
	function _(e, t) {
		if (!o.isValidNot0(t)) throw Error(`invalid signature ${e}: out of range 1..Point.Fn.ORDER`);
		return t;
	}
	function v(e, t) {
		Ri(t);
		let n = p.signature;
		return Er(e, t === "compact" ? n : t === "recovered" ? n + 1 : void 0, `${t} signature`);
	}
	class y {
		constructor(e, t, n) {
			this.r = _("r", e), this.s = _("s", t), n != null && (this.recovery = n), Object.freeze(this);
		}
		static fromBytes(e, t = h) {
			v(e, t);
			let n;
			if (t === "der") {
				let { r: t, s: n } = Bi.toSig(Er(e));
				return new y(t, n);
			}
			t === "recovered" && (n = e[0], t = "compact", e = e.subarray(1));
			let r = o.BYTES, i = e.subarray(0, r), a = e.subarray(r, r * 2);
			return new y(o.fromBytes(i), o.fromBytes(a), n);
		}
		static fromHex(e, t) {
			return this.fromBytes(se(e), t);
		}
		addRecoveryBit(e) {
			return new y(this.r, this.s, e);
		}
		recoverPublicKey(t) {
			let n = a.ORDER, { r, s: i, recovery: c } = this;
			if (c == null || ![
				0,
				1,
				2,
				3
			].includes(c)) throw Error("recovery id invalid");
			if (s * Ui < n && c > 1) throw Error("recovery id is ambiguous for h>1 curve");
			let l = c === 2 || c === 3 ? r + s : r;
			if (!a.isValid(l)) throw Error("recovery id 2 or 3 invalid");
			let u = a.toBytes(l), d = e.fromBytes(ce(Ji((c & 1) == 0), u)), f = o.inv(l), p = x(Nr("msgHash", t)), m = o.create(-p * f), h = o.create(i * f), g = e.BASE.multiplyUnsafe(m).add(d.multiplyUnsafe(h));
			if (g.is0()) throw Error("point at infinify");
			return g.assertValidity(), g;
		}
		hasHighS() {
			return g(this.s);
		}
		toBytes(e = h) {
			if (Ri(e), e === "der") return se(Bi.hexFromSig(this));
			let t = o.toBytes(this.r), n = o.toBytes(this.s);
			if (e === "recovered") {
				if (this.recovery == null) throw Error("recovery bit must be present");
				return ce(Uint8Array.of(this.recovery), t, n);
			}
			return ce(t, n);
		}
		toHex(e) {
			return ae(this.toBytes(e));
		}
		assertValidity() {}
		static fromCompact(e) {
			return y.fromBytes(Nr("sig", e), "compact");
		}
		static fromDER(e) {
			return y.fromBytes(Nr("sig", e), "der");
		}
		normalizeS() {
			return this.hasHighS() ? new y(this.r, o.neg(this.s), this.recovery) : this;
		}
		toDERRawBytes() {
			return this.toBytes("der");
		}
		toDERHex() {
			return ae(this.toBytes("der"));
		}
		toCompactRawBytes() {
			return this.toBytes("compact");
		}
		toCompactHex() {
			return ae(this.toBytes("compact"));
		}
	}
	let b = n.bits2int || function(e) {
		if (e.length > 8192) throw Error("input is too large");
		let t = kr(e), n = e.length * 8 - c;
		return n > 0 ? t >> BigInt(n) : t;
	}, x = n.bits2int_modN || function(e) {
		return o.create(b(e));
	}, C = Rr(c);
	function w(e) {
		return Ir("num < 2^" + c, e, Vi, C), o.toBytes(e);
	}
	function E(e, n) {
		return Er(e, void 0, "message"), n ? Er(t(e), void 0, "prehashed message") : e;
	}
	function D(t, n, i) {
		if (["recovered", "canonical"].some((e) => e in i)) throw Error("sign() legacy options not supported");
		let { lowS: a, prehash: s, extraEntropy: c } = zi(i, m);
		t = E(t, s);
		let l = x(t), u = Ki(o, n), d = [w(u), w(l)];
		if (c != null && c !== !1) {
			let e = c === !0 ? r(p.secretKey) : c;
			d.push(Nr("extraEntropy", e));
		}
		let f = ce(...d), h = l;
		function _(t) {
			let n = b(t);
			if (!o.isValidNot0(n)) return;
			let r = o.inv(n), i = e.BASE.multiply(n).toAffine(), s = o.create(i.x);
			if (s === Vi) return;
			let c = o.create(r * o.create(h + s * u));
			if (c === Vi) return;
			let l = (i.x === s ? 0 : 2) | Number(i.y & Hi), d = c;
			return a && g(c) && (d = o.neg(c), l ^= 1), new y(s, d, l);
		}
		return {
			seed: f,
			k2sig: _
		};
	}
	function ee(e, n, r = {}) {
		e = Nr("message", e);
		let { seed: a, k2sig: s } = D(e, n, r);
		return zr(t.outputLen, o.BYTES, i)(a, s);
	}
	function O(e) {
		let t, n = typeof e == "string" || S(e), r = !n && typeof e == "object" && !!e && typeof e.r == "bigint" && typeof e.s == "bigint";
		if (!n && !r) throw Error("invalid signature, expected Uint8Array, hex string or Signature instance");
		if (r) t = new y(e.r, e.s);
		else if (n) {
			try {
				t = y.fromBytes(Nr("sig", e), "der");
			} catch (e) {
				if (!(e instanceof Bi.Err)) throw e;
			}
			if (!t) try {
				t = y.fromBytes(Nr("sig", e), "compact");
			} catch {
				return !1;
			}
		}
		return t || !1;
	}
	function k(t, n, r, i = {}) {
		let { lowS: a, prehash: s, format: c } = zi(i, m);
		if (r = Nr("publicKey", r), n = E(Nr("message", n), s), "strict" in i) throw Error("options.strict was renamed to lowS");
		let l = c === void 0 ? O(t) : y.fromBytes(Nr("sig", t), c);
		if (l === !1) return !1;
		try {
			let t = e.fromBytes(r);
			if (a && l.hasHighS()) return !1;
			let { r: i, s } = l, c = x(n), u = o.inv(s), d = o.create(c * u), f = o.create(i * u), p = e.BASE.multiplyUnsafe(d).add(t.multiplyUnsafe(f));
			return p.is0() ? !1 : o.create(p.x) === i;
		} catch {
			return !1;
		}
	}
	function te(e, t, n = {}) {
		let { prehash: r } = zi(n, m);
		return t = E(t, r), y.fromBytes(e, "recovered").recoverPublicKey(t).toBytes();
	}
	return Object.freeze({
		keygen: l,
		getPublicKey: u,
		getSharedSecret: d,
		utils: f,
		lengths: p,
		Point: e,
		sign: ee,
		verify: k,
		recoverPublicKey: te,
		Signature: y,
		hash: t
	});
}
function ea(e) {
	let t = {
		a: e.a,
		b: e.b,
		p: e.Fp.ORDER,
		n: e.n,
		h: e.h,
		Gx: e.Gx,
		Gy: e.Gy
	}, n = e.Fp, r = e.allowedPrivateKeyLengths ? Array.from(new Set(e.allowedPrivateKeyLengths.map((e) => Math.ceil(e / 2)))) : void 0;
	return {
		CURVE: t,
		curveOpts: {
			Fp: n,
			Fn: mi(t.n, {
				BITS: e.nBitLength,
				allowedLengths: r,
				modFromBytes: e.wrapPrivateKey
			}),
			allowInfinityPoint: e.allowInfinityPoint,
			endo: e.endo,
			isTorsionFree: e.isTorsionFree,
			clearCofactor: e.clearCofactor,
			fromBytes: e.fromBytes,
			toBytes: e.toBytes
		}
	};
}
function ta(e) {
	let { CURVE: t, curveOpts: n } = ea(e), r = {
		hmac: e.hmac,
		randomBytes: e.randomBytes,
		lowS: e.lowS,
		bits2int: e.bits2int,
		bits2int_modN: e.bits2int_modN
	};
	return {
		CURVE: t,
		curveOpts: n,
		hash: e.hash,
		ecdsaOpts: r
	};
}
function na(e, t) {
	let n = t.Point;
	return Object.assign({}, t, {
		ProjectivePoint: n,
		CURVE: Object.assign({}, e, pi(n.Fn.ORDER, n.Fn.BITS))
	});
}
function ra(e) {
	let { CURVE: t, curveOpts: n, hash: r, ecdsaOpts: i } = ta(e);
	return na(e, $i(qi(t, n), r, i));
}
//#endregion
//#region node_modules/@noble/curves/esm/_shortw_utils.js
function ia(e, t) {
	let n = (t) => ra({
		...e,
		hash: t
	});
	return {
		...n(t),
		create: n
	};
}
//#endregion
//#region node_modules/@noble/curves/esm/abstract/hash-to-curve.js
var aa = kr;
function oa(e, t) {
	if (ca(e), ca(t), e < 0 || e >= 1 << 8 * t) throw Error("invalid I2OSP input: " + e);
	let n = Array.from({ length: t }).fill(0);
	for (let r = t - 1; r >= 0; r--) n[r] = e & 255, e >>>= 8;
	return new Uint8Array(n);
}
function sa(e, t) {
	let n = new Uint8Array(e.length);
	for (let r = 0; r < e.length; r++) n[r] = e[r] ^ t[r];
	return n;
}
function ca(e) {
	if (!Number.isSafeInteger(e)) throw Error("number expected");
}
function la(e) {
	if (!S(e) && typeof e != "string") throw Error("DST must be Uint8Array or string");
	return typeof e == "string" ? I(e) : e;
}
function ua(e, t, n, r) {
	w(e), ca(n), t = la(t), t.length > 255 && (t = r(ce(I("H2C-OVERSIZE-DST-"), t)));
	let { outputLen: i, blockLen: a } = r, o = Math.ceil(n / i);
	if (n > 65535 || o > 255) throw Error("expand_message_xmd: invalid lenInBytes");
	let s = ce(t, oa(t.length, 1)), c = oa(0, a), l = oa(n, 2), u = Array(o), d = r(ce(c, e, l, oa(0, 1), s));
	u[0] = r(ce(d, oa(1, 1), s));
	for (let e = 1; e <= o; e++) u[e] = r(ce(sa(d, u[e - 1]), oa(e + 1, 1), s));
	return ce(...u).slice(0, n);
}
function da(e, t, n, r, i) {
	if (w(e), ca(n), t = la(t), t.length > 255) {
		let e = Math.ceil(2 * r / 8);
		t = i.create({ dkLen: e }).update(I("H2C-OVERSIZE-DST-")).update(t).digest();
	}
	if (n > 65535 || t.length > 255) throw Error("expand_message_xof: invalid lenInBytes");
	return i.create({ dkLen: n }).update(e).update(oa(n, 2)).update(t).update(oa(t.length, 1)).digest();
}
function fa(e, t, n) {
	Vr(n, {
		p: "bigint",
		m: "number",
		k: "number",
		hash: "function"
	});
	let { p: r, k: i, m: a, hash: o, expand: s, DST: c } = n;
	if (!Br(n.hash)) throw Error("expected valid hash");
	w(e), ca(t);
	let l = r.toString(2).length, u = Math.ceil((l + i) / 8), d = t * a * u, f;
	if (s === "xmd") f = ua(e, c, d, o);
	else if (s === "xof") f = da(e, c, d, i, o);
	else if (s === "_internal_pass") f = e;
	else throw Error("expand must be \"xmd\" or \"xof\"");
	let p = Array(t);
	for (let e = 0; e < t; e++) {
		let t = Array(a);
		for (let n = 0; n < a; n++) {
			let i = u * (n + e * a);
			t[n] = $r(aa(f.subarray(i, i + u)), r);
		}
		p[e] = t;
	}
	return p;
}
function pa(e, t) {
	let n = t.map((e) => Array.from(e).reverse());
	return (t, r) => {
		let [i, a, o, s] = n.map((n) => n.reduce((n, r) => e.add(e.mul(n, t), r))), [c, l] = di(e, [a, s], !0);
		return t = e.mul(i, c), r = e.mul(r, e.mul(o, l)), {
			x: t,
			y: r
		};
	};
}
var ma = I("HashToScalar-");
function ha(e, t, n) {
	if (typeof t != "function") throw Error("mapToCurve() must be defined");
	function r(n) {
		return e.fromAffine(t(n));
	}
	function i(t) {
		let n = t.clearCofactor();
		return n.equals(e.ZERO) ? e.ZERO : (n.assertValidity(), n);
	}
	return {
		defaults: n,
		hashToCurve(e, t) {
			let a = fa(e, 2, Object.assign({}, n, t)), o = r(a[0]), s = r(a[1]);
			return i(o.add(s));
		},
		encodeToCurve(e, t) {
			let a = n.encodeDST ? { DST: n.encodeDST } : {};
			return i(r(fa(e, 1, Object.assign({}, n, a, t))[0]));
		},
		mapToCurve(e) {
			if (!Array.isArray(e)) throw Error("expected array of bigints");
			for (let t of e) if (typeof t != "bigint") throw Error("expected array of bigints");
			return i(r(e));
		},
		hashToScalar(t, r) {
			let i = e.Fn.ORDER;
			return fa(t, 1, Object.assign({}, n, {
				p: i,
				m: 1,
				DST: ma
			}, r))[0][0];
		}
	};
}
//#endregion
//#region node_modules/@noble/curves/esm/secp256k1.js
var ga = {
	p: BigInt("0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"),
	n: BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"),
	h: BigInt(1),
	a: BigInt(0),
	b: BigInt(7),
	Gx: BigInt("0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),
	Gy: BigInt("0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8")
}, _a = {
	beta: BigInt("0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee"),
	basises: [[BigInt("0x3086d221a7d46bcde86c90e49284eb15"), -BigInt("0xe4437ed6010e88286f547fa90abfe4c3")], [BigInt("0x114ca50f7a8e2f3f657c1108d9d44cfd8"), BigInt("0x3086d221a7d46bcde86c90e49284eb15")]]
}, va = /* @__PURE__ */ BigInt(0), ya = /* @__PURE__ */ BigInt(1), ba = /* @__PURE__ */ BigInt(2);
function xa(e) {
	let t = ga.p, n = BigInt(3), r = BigInt(6), i = BigInt(11), a = BigInt(22), o = BigInt(23), s = BigInt(44), c = BigInt(88), l = e * e * e % t, u = l * l * e % t, d = ei(ei(ei(u, n, t) * u % t, n, t) * u % t, ba, t) * l % t, f = ei(d, i, t) * d % t, p = ei(f, a, t) * f % t, m = ei(p, s, t) * p % t, h = ei(ei(ei(ei(ei(ei(m, c, t) * m % t, s, t) * p % t, n, t) * u % t, o, t) * f % t, r, t) * l % t, ba, t);
	if (!Sa.eql(Sa.sqr(h), e)) throw Error("Cannot find square root");
	return h;
}
var Sa = mi(ga.p, { sqrt: xa }), Ca = ia({
	...ga,
	Fp: Sa,
	lowS: !0,
	endo: _a
}, Sr), wa = {};
function Ta(e, ...t) {
	let n = wa[e];
	if (n === void 0) {
		let t = Sr(I(e));
		n = ce(t, t), wa[e] = n;
	}
	return Sr(ce(n, ...t));
}
var Ea = (e) => e.toBytes(!0).slice(1), Da = Ca.Point, Oa = (e) => e % ba === va;
function ka(e) {
	let { Fn: t, BASE: n } = Da, r = Ki(t, e), i = n.multiply(r);
	return {
		scalar: Oa(i.y) ? r : t.neg(r),
		bytes: Ea(i)
	};
}
function Aa(e) {
	let t = Sa;
	if (!t.isValidNot0(e)) throw Error("invalid x: Fail if x ≥ p");
	let n = t.create(e * e), r = t.create(n * e + BigInt(7)), i = t.sqrt(r);
	Oa(i) || (i = t.neg(i));
	let a = Da.fromAffine({
		x: e,
		y: i
	});
	return a.assertValidity(), a;
}
var ja = kr;
function Ma(...e) {
	return Da.Fn.create(ja(Ta("BIP0340/challenge", ...e)));
}
function Na(e) {
	return ka(e).bytes;
}
function Pa(e, t, n = z(32)) {
	let { Fn: r } = Da, i = Nr("message", e), { bytes: a, scalar: o } = ka(t), s = Nr("auxRand", n, 32), { bytes: c, scalar: l } = ka(Ta("BIP0340/nonce", r.toBytes(o ^ ja(Ta("BIP0340/aux", s))), a, i)), u = Ma(c, a, i), d = new Uint8Array(64);
	if (d.set(c, 0), d.set(r.toBytes(r.create(l + u * o)), 32), !Fa(d, i, a)) throw Error("sign: Invalid signature produced");
	return d;
}
function Fa(e, t, n) {
	let { Fn: r, BASE: i } = Da, a = Nr("signature", e, 64), o = Nr("message", t), s = Nr("publicKey", n, 32);
	try {
		let e = Aa(ja(s)), t = ja(a.subarray(0, 32));
		if (!Fr(t, ya, ga.p)) return !1;
		let n = ja(a.subarray(32, 64));
		if (!Fr(n, ya, ga.n)) return !1;
		let c = Ma(r.toBytes(t), Ea(e), o), l = i.multiplyUnsafe(n).add(e.multiplyUnsafe(r.neg(c))), { x: u, y: d } = l.toAffine();
		return !(l.is0() || !Oa(d) || u !== t);
	} catch {
		return !1;
	}
}
var Ia = /* @__PURE__ */ (() => {
	let e = (e = z(48)) => _i(e, ga.n);
	Ca.utils.randomSecretKey;
	function t(t) {
		let n = e(t);
		return {
			secretKey: n,
			publicKey: Na(n)
		};
	}
	return {
		keygen: t,
		getPublicKey: Na,
		sign: Pa,
		verify: Fa,
		Point: Da,
		utils: {
			randomSecretKey: e,
			randomPrivateKey: e,
			taggedHash: Ta,
			lift_x: Aa,
			pointToBytes: Ea,
			numberToBytesBE: jr,
			bytesToNumberBE: kr,
			mod: $r
		},
		lengths: {
			secretKey: 32,
			publicKey: 32,
			publicKeyHasPrefix: !1,
			signature: 64,
			seed: 48
		}
	};
})(), La = pa(Sa, [
	[
		"0x8e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38daaaaa8c7",
		"0x7d3d4c80bc321d5b9f315cea7fd44c5d595d2fc0bf63b92dfff1044f17c6581",
		"0x534c328d23f234e6e2a413deca25caece4506144037c40314ecbd0b53d9dd262",
		"0x8e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38daaaaa88c"
	],
	[
		"0xd35771193d94918a9ca34ccbb7b640dd86cd409542f8487d9fe6b745781eb49b",
		"0xedadc6f64383dc1df7c4b2d51b54225406d36b641f5e41bbc52a56612a8c6d14",
		"0x0000000000000000000000000000000000000000000000000000000000000001"
	],
	[
		"0x4bda12f684bda12f684bda12f684bda12f684bda12f684bda12f684b8e38e23c",
		"0xc75e0c32d5cb7c0fa9d0a54b12a0a6d5647ab046d686da6fdffc90fc201d71a3",
		"0x29a6194691f91a73715209ef6512e576722830a201be2018a765e85a9ecee931",
		"0x2f684bda12f684bda12f684bda12f684bda12f684bda12f684bda12f38e38d84"
	],
	[
		"0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffff93b",
		"0x7a06534bb8bdb49fd5e9e6632722c2989467c1bfc8e8d978dfb425d2685c2573",
		"0x6484aa716545ca2cf3a70c3fa8fe337e0a3d21162f0d6299a7bf8192bfd2a76f",
		"0x0000000000000000000000000000000000000000000000000000000000000001"
	]
].map((e) => e.map((e) => BigInt(e)))), Ra = Xi(Sa, {
	A: BigInt("0x3f8731abdd661adca08a5558f0f5d272e953d363cb6f0e5d405447c01a444533"),
	B: BigInt("1771"),
	Z: Sa.create(BigInt("-11"))
}), za = ha(Ca.Point, (e) => {
	let { x: t, y: n } = Ra(Sa.create(e[0]));
	return La(t, n);
}, {
	DST: "secp256k1_XMD:SHA-256_SSWU_RO_",
	encodeDST: "secp256k1_XMD:SHA-256_SSWU_NU_",
	p: Sa.ORDER,
	m: 1,
	k: 128,
	expand: "xmd",
	hash: Sr
});
za.hashToCurve, za.encodeToCurve;
//#endregion
//#region node_modules/@noble/hashes/esm/legacy.js
var Ba = /* @__PURE__ */ Uint8Array.from([
	7,
	4,
	13,
	1,
	10,
	6,
	15,
	3,
	12,
	0,
	9,
	5,
	2,
	14,
	11,
	8
]), Va = Uint8Array.from(Array(16).fill(0).map((e, t) => t)), Ha = Va.map((e) => (9 * e + 5) % 16), Ua = /* @__PURE__ */ (() => {
	let e = [[Va], [Ha]];
	for (let t = 0; t < 4; t++) for (let n of e) n.push(n[t].map((e) => Ba[e]));
	return e;
})(), Wa = Ua[0], Ga = Ua[1], Ka = /* @__PURE__ */ [
	[
		11,
		14,
		15,
		12,
		5,
		8,
		7,
		9,
		11,
		13,
		14,
		15,
		6,
		7,
		9,
		8
	],
	[
		12,
		13,
		11,
		15,
		6,
		9,
		9,
		7,
		12,
		15,
		11,
		13,
		7,
		8,
		7,
		7
	],
	[
		13,
		15,
		14,
		11,
		7,
		7,
		6,
		8,
		13,
		14,
		13,
		12,
		5,
		5,
		6,
		9
	],
	[
		14,
		11,
		12,
		14,
		8,
		6,
		5,
		5,
		15,
		12,
		15,
		14,
		9,
		9,
		8,
		6
	],
	[
		15,
		12,
		13,
		13,
		9,
		5,
		8,
		6,
		14,
		11,
		12,
		11,
		8,
		6,
		5,
		5
	]
].map((e) => Uint8Array.from(e)), qa = /* @__PURE__ */ Wa.map((e, t) => e.map((e) => Ka[t][e])), Ja = /* @__PURE__ */ Ga.map((e, t) => e.map((e) => Ka[t][e])), Ya = /* @__PURE__ */ Uint32Array.from([
	0,
	1518500249,
	1859775393,
	2400959708,
	2840853838
]), Xa = /* @__PURE__ */ Uint32Array.from([
	1352829926,
	1548603684,
	1836072691,
	2053994217,
	0
]);
function Za(e, t, n, r) {
	return e === 0 ? t ^ n ^ r : e === 1 ? t & n | ~t & r : e === 2 ? (t | ~n) ^ r : e === 3 ? t & r | n & ~r : t ^ (n | ~r);
}
var Qa = /* @__PURE__ */ new Uint32Array(16), $a = class extends me {
	constructor() {
		super(64, 20, 8, !0), this.h0 = 1732584193, this.h1 = -271733879, this.h2 = -1732584194, this.h3 = 271733878, this.h4 = -1009589776;
	}
	get() {
		let { h0: e, h1: t, h2: n, h3: r, h4: i } = this;
		return [
			e,
			t,
			n,
			r,
			i
		];
	}
	set(e, t, n, r, i) {
		this.h0 = e | 0, this.h1 = t | 0, this.h2 = n | 0, this.h3 = r | 0, this.h4 = i | 0;
	}
	process(e, t) {
		for (let n = 0; n < 16; n++, t += 4) Qa[n] = e.getUint32(t, !0);
		let n = this.h0 | 0, r = n, i = this.h1 | 0, a = i, o = this.h2 | 0, s = o, c = this.h3 | 0, l = c, u = this.h4 | 0, d = u;
		for (let e = 0; e < 5; e++) {
			let t = 4 - e, f = Ya[e], p = Xa[e], m = Wa[e], h = Ga[e], g = qa[e], _ = Ja[e];
			for (let t = 0; t < 16; t++) {
				let r = A(n + Za(e, i, o, c) + Qa[m[t]] + f, g[t]) + u | 0;
				n = u, u = c, c = A(o, 10) | 0, o = i, i = r;
			}
			for (let e = 0; e < 16; e++) {
				let n = A(r + Za(t, a, s, l) + Qa[h[e]] + p, _[e]) + d | 0;
				r = d, d = l, l = A(s, 10) | 0, s = a, a = n;
			}
		}
		this.set(this.h1 + o + l | 0, this.h2 + c + d | 0, this.h3 + u + r | 0, this.h4 + n + a | 0, this.h0 + i + s | 0);
	}
	roundClean() {
		O(Qa);
	}
	destroy() {
		this.destroyed = !0, O(this.buffer), this.set(0, 0, 0, 0, 0);
	}
}, eo = /* @__PURE__ */ le(() => new $a()), to = Sr;
//#endregion
//#region node_modules/base-x/src/esm/index.js
function no(e) {
	if (e.length >= 255) throw TypeError("Alphabet too long");
	let t = new Uint8Array(256);
	for (let e = 0; e < t.length; e++) t[e] = 255;
	for (let n = 0; n < e.length; n++) {
		let r = e.charAt(n), i = r.charCodeAt(0);
		if (t[i] !== 255) throw TypeError(r + " is ambiguous");
		t[i] = n;
	}
	let n = e.length, r = e.charAt(0), i = Math.log(n) / Math.log(256), a = Math.log(256) / Math.log(n);
	function o(t) {
		if (t instanceof Uint8Array || (ArrayBuffer.isView(t) ? t = new Uint8Array(t.buffer, t.byteOffset, t.byteLength) : Array.isArray(t) && (t = Uint8Array.from(t))), !(t instanceof Uint8Array)) throw TypeError("Expected Uint8Array");
		if (t.length === 0) return "";
		let i = 0, o = 0, s = 0, c = t.length;
		for (; s !== c && t[s] === 0;) s++, i++;
		let l = (c - s) * a + 1 >>> 0, u = new Uint8Array(l);
		for (; s !== c;) {
			let e = t[s], r = 0;
			for (let t = l - 1; (e !== 0 || r < o) && t !== -1; t--, r++) e += 256 * u[t] >>> 0, u[t] = e % n >>> 0, e = e / n >>> 0;
			if (e !== 0) throw Error("Non-zero carry");
			o = r, s++;
		}
		let d = l - o;
		for (; d !== l && u[d] === 0;) d++;
		let f = r.repeat(i);
		for (; d < l; ++d) f += e.charAt(u[d]);
		return f;
	}
	function s(e) {
		if (typeof e != "string") throw TypeError("Expected String");
		if (e.length === 0) return new Uint8Array();
		let a = 0, o = 0, s = 0;
		for (; e[a] === r;) o++, a++;
		let c = (e.length - a) * i + 1 >>> 0, l = new Uint8Array(c);
		for (; a < e.length;) {
			let r = e.charCodeAt(a);
			if (r > 255) return;
			let i = t[r];
			if (i === 255) return;
			let o = 0;
			for (let e = c - 1; (i !== 0 || o < s) && e !== -1; e--, o++) i += n * l[e] >>> 0, l[e] = i % 256 >>> 0, i = i / 256 >>> 0;
			if (i !== 0) throw Error("Non-zero carry");
			s = o, a++;
		}
		let u = c - s;
		for (; u !== c && l[u] === 0;) u++;
		let d = new Uint8Array(o + (c - u)), f = o;
		for (; u !== c;) d[f++] = l[u++];
		return d;
	}
	function c(e) {
		let t = s(e);
		if (t) return t;
		throw Error("Non-base" + n + " character");
	}
	return {
		encode: o,
		decodeUnsafe: s,
		decode: c
	};
}
var ro = no("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz");
//#endregion
//#region node_modules/bs58check/src/esm/base.js
function io(e) {
	function t(t) {
		var n = Uint8Array.from(t), r = e(n), i = n.length + 4, a = new Uint8Array(i);
		return a.set(n, 0), a.set(r.subarray(0, 4), n.length), ro.encode(a);
	}
	function n(t) {
		var n = t.slice(0, -4), r = t.slice(-4), i = e(n);
		if (!(r[0] ^ i[0] | r[1] ^ i[1] | r[2] ^ i[2] | r[3] ^ i[3])) return n;
	}
	function r(e) {
		var t = ro.decodeUnsafe(e);
		if (t != null) return n(t);
	}
	function i(e) {
		var t = n(ro.decode(e));
		if (t == null) throw Error("Invalid checksum");
		return t;
	}
	return {
		encode: t,
		decode: i,
		decodeUnsafe: r
	};
}
//#endregion
//#region node_modules/bs58check/src/esm/index.js
function ao(e) {
	return to(to(e));
}
var oo = io(ao);
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/btc/verify.js
function so(e) {
	let t = q(e);
	return t < 253 ? ze(t, 1) : t <= 65535 ? _([253], ze(t, 2)) : t <= 4294967295 ? _([254], ze(t, 4)) : _([255], ze(t, 8));
}
function co(e, t) {
	let n = t ?? "Bitcoin Signed Message:\n", r = typeof n == "string" ? y(n, "utf8") : y(n), i = typeof e == "string" ? y(e, "utf8") : y(e);
	return Sr(Sr(_(r, so(i.length), i)));
}
function lo(e) {
	return eo(Sr(y(e)));
}
function uo(e) {
	return K(oo.decode(e).slice(1));
}
function fo(e, t, n) {
	let r = typeof e == "string" ? e : K(e).slice(2), i = y(t, "base64").slice(1);
	return Ca.verify(y(i), co(r), y(n));
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/ckb/verifyCkbSecp256k1.js
function po(e) {
	return Pe(y(`Nervos Message:${typeof e == "string" ? e : K(e)}`, "utf8"));
}
function mo(e, t, n) {
	let r = y(t);
	return Ca.verify(new Ca.Signature(q(r.slice(0, 32)), q(r.slice(32, 64))).addRecoveryBit(Number(q(r.slice(64, 65)))).toBytes(), y(po(e)), y(n));
}
function ho(e, t) {
	let n, r, i, a = "";
	for (n in e) if ((i = e[n]) !== void 0) if (Array.isArray(i)) for (r = 0; r < i.length; r++) a && (a += "&"), a += `${encodeURIComponent(n)}=${encodeURIComponent(i[r])}`;
	else a && (a += "&"), a += `${encodeURIComponent(n)}=${encodeURIComponent(i)}`;
	return (t || "") + a;
}
function go(e, t) {
	function n(n) {
		if (typeof n == "object" && n) try {
			return e(n);
		} catch {}
		else if (typeof n == "string" && typeof t == "function") try {
			return t(n), e(n);
		} catch {}
		return n;
	}
	return (e) => {
		e = { ...e }, e && Object.keys(e).forEach((t) => {
			let r = e[t];
			r === void 0 || r === void 0 ? delete e[t] : e[t] = n(r);
		});
		let t = ho(e).toString();
		return t ? `?${t}` : "";
	};
}
var _o = go(JSON.stringify, JSON.parse);
function vo(e) {
	let t = e.replace(/-/g, "+").replace(/_/g, "/"), n = (4 - t.length % 4) % 4, r = t.padEnd(t.length + n, "="), i = atob(r), a = new ArrayBuffer(i.length), o = new Uint8Array(a);
	for (let e = 0; e < i.length; e++) o[e] = i.charCodeAt(e);
	return a;
}
function yo(e) {
	let t = new Uint8Array(e), n = "";
	for (let e = 0; e < t.length; e++) {
		let r = t[e];
		r != null && (n += String.fromCharCode(r));
	}
	return btoa(n).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}
function bo(e) {
	let t = new Uint8Array(e.length / 2);
	for (let n = 0; n < e.length; n += 2) t[n / 2] = Number.parseInt(e.substring(n, n + 2), 16);
	return t.buffer;
}
function xo(e) {
	return [...new Uint8Array(e)].map((e) => e.toString(16).padStart(2, "0")).join("");
}
function So(e, t) {
	let n = new Uint8Array(e.byteLength + t.byteLength);
	return n.set(new Uint8Array(e), 0), n.set(new Uint8Array(t), e.byteLength), n.buffer;
}
function Co(e) {
	return new TextEncoder().encode(e);
}
function wo(e) {
	let t = "";
	for (let n = 0; n < e.length; n += 2) t += String.fromCharCode(Number.parseInt(e.substr(n, 2), 16));
	return t;
}
function To() {
	return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
}
var Eo = /* @__PURE__ */ ((e) => (e[e.RS256 = -257] = "RS256", e[e.ES256 = -7] = "ES256", e))(Eo || {}), Do = /* @__PURE__ */ ((e) => (e.Auth = "Auth", e.SignMessage = "SignMessage", e.SignEvm = "SignEvm", e.SignPsbt = "SignPsbt", e.BatchSignPsbt = "BatchSignPsbt", e.SignCkbTx = "SignCkbTx", e.SignCotaNFT = "SignCotaNFT", e.SignCkbRawTx = "SignCkbRawTx", e.SignNostrEvent = "SignNostrEvent", e.EncryptNostrMessage = "EncryptNostrMessage", e.EvmWeb2Login = "EvmWeb2Login", e.DecryptNostrMessage = "DecryptNostrMessage", e.AuthMiniApp = "AuthMiniApp", e.SignMiniAppMessage = "SignMiniAppMessage", e.SignMiniAppEvm = "SignMiniAppEvm", e))(Do || {}), Oo = { joyidAppURL: "https://testnet.joyid.dev" }, ko = () => Oo, Ao = class e extends Error {
	constructor(t, n) {
		super(n), this.error = t, this.error_description = n, Object.setPrototypeOf(this, e.prototype);
	}
}, jo = class e extends Ao {
	constructor() {
		super("timeout", "Timeout"), Object.setPrototypeOf(this, e.prototype);
	}
}, Mo = class e extends jo {
	constructor(t) {
		super(), this.popup = t, Object.setPrototypeOf(this, e.prototype);
	}
}, No = class e extends Ao {
	constructor(t) {
		super("cancelled", "Popup closed"), this.popup = t, Object.setPrototypeOf(this, e.prototype);
	}
}, Po = class extends Ao {
	constructor(e) {
		super("NotSupported", "Popup window is blocked by browser. see: https://docs.joy.id/guide/best-practice#popup-window-blocked"), this.popup = e, Object.setPrototypeOf(this, No.prototype);
	}
}, Fo = "joyid-redirect", Io = (e, t, n) => {
	let r = e.joyidAppURL ?? ko().joyidAppURL, i = new URL(`${r}`);
	i.pathname = n;
	let a = e.redirectURL;
	if (t === "redirect") {
		let e = new URL(a);
		e.searchParams.set(Fo, "true"), a = e.href;
	}
	i.searchParams.set("type", t);
	let o = _o({
		...e,
		redirectURL: a
	});
	return i.searchParams.set("_data_", o), i.href;
}, Lo = (e = "") => {
	let t = window.screenX + (window.innerWidth - 400) / 2, n = window.screenY + (window.innerHeight - 600) / 2;
	return window.open(e, "joyid:authorize:popup", `left=${t},top=${n},width=400,height=600,resizable,scrollbars=yes,status=1`);
}, Ro = "joyid-block-dialog-style", zo = "joyid-block-dialog-approve", Bo = "joyid-block-dialog-reject", Vo = `
.joyid-block-dialog {
  position: fixed;
  top: 32px;
  left: 50%;
  width: 340px;
  margin-left: -170px;
  background: white;
  color: #333;
  display: flex;
  flex-flow: row nowrap;
  justify-content: space-between;
  align-items: center;
  height: 110px;
  z-index: 100002;
  box-sizing: border-box;
  border: 1px solid #ffffff;
  border-radius: 8px;
  padding: 16px 20px;
}
.joyid-block-dialog-bg {
  width: 100%;
  height: 100%;
  background-color: rgba(0,0,0,0.5);
  position: fixed;
  top: 0;
  left: 0;
  display: none;
  z-index: 100001;
  display: block;
}
.joyid-block-dialog-title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 8px;
}
.joyid-block-dialog-tip {
  font-size: 12px;
  color: #777;
}
.joyid-block-dialog-btn {
  width: 90px;
  height: 35px;
  font-size: 12px;
  text-align: center;
  border-radius: 6px;
  cursor: pointer;
}
.joyid-block-dialog-action {
  text-align: right;
}
#${zo} {
  border: 1px solid #333;
  color: #333;
  background: #D2FF00;
  margin-bottom: 8px;
}

#${Bo} {
  background: transparent;
}
`, Ho = `
<div class="joyid-block-dialog">
  <div class="joyid-block-dialog-content">
    <div class="joyid-block-dialog-title">
      Request Pop-up
    </div>
    <div class="joyid-block-dialog-tip">
      Click Approve to complete creating or using wallet
    </div>
  </div>
  <div class="joyid-block-dialog-action">
    <button class="joyid-block-dialog-btn" id="${zo}">Approve</button>
    <button class="joyid-block-dialog-btn" id="${Bo}">Reject</button>
  </div>
</div>
`, Uo = () => {
	if (document.getElementById(Ro) != null) return;
	let e = document.createElement("style");
	e.appendChild(document.createTextNode(Vo)), (document.head ?? document.getElementsByTagName("head")[0]).appendChild(e);
}, Wo = async (e) => {
	Uo();
	let t = document.createElement("div");
	t.innerHTML = Ho, document.body.appendChild(t);
	let n = document.createElement("div");
	n.className = "joyid-block-dialog-bg", document.body.appendChild(n);
	let r = document.getElementById(zo), i = document.getElementById(Bo), a = () => {
		document.body.removeChild(t), document.body.removeChild(n);
	};
	return new Promise((t, n) => {
		r?.addEventListener("click", async () => {
			try {
				let n = await e();
				a(), t(n);
			} catch (e) {
				a(), n(e);
			}
		}), i?.addEventListener("click", () => {
			a(), n(/* @__PURE__ */ Error("User Rejected"));
		});
	});
}, Go = /* @__PURE__ */ s(((e, t) => {
	(function(n, r) {
		typeof e == "object" && t !== void 0 ? t.exports = r() : typeof define == "function" && define.amd ? define(r) : (n ||= self, n.JSBI = r());
	})(e, function() {
		function e(t) {
			"@babel/helpers - typeof";
			return e = typeof Symbol == "function" && typeof Symbol.iterator == "symbol" ? function(e) {
				return typeof e;
			} : function(e) {
				return e && typeof Symbol == "function" && e.constructor === Symbol && e !== Symbol.prototype ? "symbol" : typeof e;
			}, e(t);
		}
		function t(e, t) {
			if (!(e instanceof t)) throw TypeError("Cannot call a class as a function");
		}
		function n(e, t) {
			for (var n, r = 0; r < t.length; r++) n = t[r], n.enumerable = n.enumerable || !1, n.configurable = !0, "value" in n && (n.writable = !0), Object.defineProperty(e, n.key, n);
		}
		function r(e, t, r) {
			return t && n(e.prototype, t), r && n(e, r), e;
		}
		function i(e, t) {
			if (typeof t != "function" && t !== null) throw TypeError("Super expression must either be null or a function");
			e.prototype = Object.create(t && t.prototype, { constructor: {
				value: e,
				writable: !0,
				configurable: !0
			} }), t && o(e, t);
		}
		function a(e) {
			return a = Object.setPrototypeOf ? Object.getPrototypeOf : function(e) {
				return e.__proto__ || Object.getPrototypeOf(e);
			}, a(e);
		}
		function o(e, t) {
			return o = Object.setPrototypeOf || function(e, t) {
				return e.__proto__ = t, e;
			}, o(e, t);
		}
		function s() {
			if (typeof Reflect > "u" || !Reflect.construct || Reflect.construct.sham) return !1;
			if (typeof Proxy == "function") return !0;
			try {
				return Date.prototype.toString.call(Reflect.construct(Date, [], function() {})), !0;
			} catch {
				return !1;
			}
		}
		function c() {
			return c = s() ? Reflect.construct : function(e, t, n) {
				var r = [null];
				r.push.apply(r, t);
				var i = new (Function.bind.apply(e, r))();
				return n && o(i, n.prototype), i;
			}, c.apply(null, arguments);
		}
		function l(e) {
			return Function.toString.call(e).indexOf("[native code]") !== -1;
		}
		function u(e) {
			var t = typeof Map == "function" ? /* @__PURE__ */ new Map() : void 0;
			return u = function(e) {
				function n() {
					return c(e, arguments, a(this).constructor);
				}
				if (e === null || !l(e)) return e;
				if (typeof e != "function") throw TypeError("Super expression must either be null or a function");
				if (t !== void 0) {
					if (t.has(e)) return t.get(e);
					t.set(e, n);
				}
				return n.prototype = Object.create(e.prototype, { constructor: {
					value: n,
					enumerable: !1,
					writable: !0,
					configurable: !0
				} }), o(n, e);
			}, u(e);
		}
		function d(e) {
			if (e === void 0) throw ReferenceError("this hasn't been initialised - super() hasn't been called");
			return e;
		}
		function f(e, t) {
			return t && (typeof t == "object" || typeof t == "function") ? t : d(e);
		}
		function p(e) {
			var t = s();
			return function() {
				var n, r = a(e);
				if (t) {
					var i = a(this).constructor;
					n = Reflect.construct(r, arguments, i);
				} else n = r.apply(this, arguments);
				return f(this, n);
			};
		}
		function m(e, t) {
			if (e) {
				if (typeof e == "string") return h(e, t);
				var n = Object.prototype.toString.call(e).slice(8, -1);
				return n === "Object" && e.constructor && (n = e.constructor.name), n === "Map" || n === "Set" ? Array.from(e) : n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n) ? h(e, t) : void 0;
			}
		}
		function h(e, t) {
			(t == null || t > e.length) && (t = e.length);
			for (var n = 0, r = Array(t); n < t; n++) r[n] = e[n];
			return r;
		}
		function g(e, t) {
			var n;
			if (typeof Symbol > "u" || e[Symbol.iterator] == null) {
				if (Array.isArray(e) || (n = m(e)) || t && e && typeof e.length == "number") {
					n && (e = n);
					var r = 0, i = function() {};
					return {
						s: i,
						n: function() {
							return r >= e.length ? { done: !0 } : {
								done: !1,
								value: e[r++]
							};
						},
						e: function(e) {
							throw e;
						},
						f: i
					};
				}
				throw TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.");
			}
			var a, o = !0, s = !1;
			return {
				s: function() {
					n = e[Symbol.iterator]();
				},
				n: function() {
					var e = n.next();
					return o = e.done, e;
				},
				e: function(e) {
					s = !0, a = e;
				},
				f: function() {
					try {
						o || n.return == null || n.return();
					} finally {
						if (s) throw a;
					}
				}
			};
		}
		var _ = function(n) {
			var a = Math.abs, o = Math.max, s = Math.imul, c = Math.clz32;
			function l(e, n) {
				var r;
				if (t(this, l), e > l.__kMaxLength) throw RangeError("Maximum BigInt size exceeded");
				return r = u.call(this, e), r.sign = n, r;
			}
			i(l, n);
			var u = p(l);
			return r(l, [
				{
					key: "toDebugString",
					value: function() {
						var e, t = ["BigInt["], n = g(this);
						try {
							for (n.s(); !(e = n.n()).done;) {
								var r = e.value;
								t.push((r && (r >>> 0).toString(16)) + ", ");
							}
						} catch (e) {
							n.e(e);
						} finally {
							n.f();
						}
						return t.push("]"), t.join("");
					}
				},
				{
					key: "toString",
					value: function() {
						var e = 0 < arguments.length && arguments[0] !== void 0 ? arguments[0] : 10;
						if (2 > e || 36 < e) throw RangeError("toString() radix argument must be between 2 and 36");
						return this.length === 0 ? "0" : e & e - 1 ? l.__toStringGeneric(this, e, !1) : l.__toStringBasePowerOfTwo(this, e);
					}
				},
				{
					key: "__copy",
					value: function() {
						for (var e = new l(this.length, this.sign), t = 0; t < this.length; t++) e[t] = this[t];
						return e;
					}
				},
				{
					key: "__trim",
					value: function() {
						for (var e = this.length, t = this[e - 1]; t === 0;) e--, t = this[e - 1], this.pop();
						return e === 0 && (this.sign = !1), this;
					}
				},
				{
					key: "__initializeDigits",
					value: function() {
						for (var e = 0; e < this.length; e++) this[e] = 0;
					}
				},
				{
					key: "__clzmsd",
					value: function() {
						return c(this[this.length - 1]);
					}
				},
				{
					key: "__inplaceMultiplyAdd",
					value: function(e, t, n) {
						n > this.length && (n = this.length);
						for (var r = 65535 & e, i = e >>> 16, a = 0, o = 65535 & t, c = t >>> 16, l = 0; l < n; l++) {
							var u = this.__digit(l), d = 65535 & u, f = u >>> 16, p = s(d, r), m = s(d, i), h = s(f, r), g = s(f, i), _ = o + (65535 & p), v = c + a + (_ >>> 16) + (p >>> 16) + (65535 & m) + (65535 & h);
							o = (m >>> 16) + (h >>> 16) + (65535 & g) + (v >>> 16), a = o >>> 16, o &= 65535, c = g >>> 16, this.__setDigit(l, 65535 & _ | v << 16);
						}
						if (a !== 0 || o !== 0 || c !== 0) throw Error("implementation bug");
					}
				},
				{
					key: "__inplaceAdd",
					value: function(e, t, n) {
						for (var r, i = 0, a = 0; a < n; a++) r = this.__halfDigit(t + a) + e.__halfDigit(a) + i, i = r >>> 16, this.__setHalfDigit(t + a, r);
						return i;
					}
				},
				{
					key: "__inplaceSub",
					value: function(e, t, n) {
						var r = 0;
						if (1 & t) {
							t >>= 1;
							for (var i = this.__digit(t), a = 65535 & i, o = 0; o < n - 1 >>> 1; o++) {
								var s = e.__digit(o), c = (i >>> 16) - (65535 & s) - r;
								r = 1 & c >>> 16, this.__setDigit(t + o, c << 16 | 65535 & a), i = this.__digit(t + o + 1), a = (65535 & i) - (s >>> 16) - r, r = 1 & a >>> 16;
							}
							var l = e.__digit(o), u = (i >>> 16) - (65535 & l) - r;
							if (r = 1 & u >>> 16, this.__setDigit(t + o, u << 16 | 65535 & a), t + o + 1 >= this.length) throw RangeError("out of bounds");
							!(1 & n) && (i = this.__digit(t + o + 1), a = (65535 & i) - (l >>> 16) - r, r = 1 & a >>> 16, this.__setDigit(t + e.length, 4294901760 & i | 65535 & a));
						} else {
							t >>= 1;
							for (var d = 0; d < e.length - 1; d++) {
								var f = this.__digit(t + d), p = e.__digit(d), m = (65535 & f) - (65535 & p) - r;
								r = 1 & m >>> 16;
								var h = (f >>> 16) - (p >>> 16) - r;
								r = 1 & h >>> 16, this.__setDigit(t + d, h << 16 | 65535 & m);
							}
							var g = this.__digit(t + d), _ = e.__digit(d), v = (65535 & g) - (65535 & _) - r;
							r = 1 & v >>> 16;
							var y = 0;
							!(1 & n) && (y = (g >>> 16) - (_ >>> 16) - r, r = 1 & y >>> 16), this.__setDigit(t + d, y << 16 | 65535 & v);
						}
						return r;
					}
				},
				{
					key: "__inplaceRightShift",
					value: function(e) {
						if (e !== 0) {
							for (var t, n = this.__digit(0) >>> e, r = this.length - 1, i = 0; i < r; i++) t = this.__digit(i + 1), this.__setDigit(i, t << 32 - e | n), n = t >>> e;
							this.__setDigit(r, n);
						}
					}
				},
				{
					key: "__digit",
					value: function(e) {
						return this[e];
					}
				},
				{
					key: "__unsignedDigit",
					value: function(e) {
						return this[e] >>> 0;
					}
				},
				{
					key: "__setDigit",
					value: function(e, t) {
						this[e] = 0 | t;
					}
				},
				{
					key: "__setDigitGrow",
					value: function(e, t) {
						this[e] = 0 | t;
					}
				},
				{
					key: "__halfDigitLength",
					value: function() {
						var e = this.length;
						return 65535 >= this.__unsignedDigit(e - 1) ? 2 * e - 1 : 2 * e;
					}
				},
				{
					key: "__halfDigit",
					value: function(e) {
						return 65535 & this[e >>> 1] >>> ((1 & e) << 4);
					}
				},
				{
					key: "__setHalfDigit",
					value: function(e, t) {
						var n = e >>> 1, r = this.__digit(n), i = 1 & e ? 65535 & r | t << 16 : 4294901760 & r | 65535 & t;
						this.__setDigit(n, i);
					}
				}
			], [
				{
					key: "BigInt",
					value: function(t) {
						var n = Math.floor, r = Number.isFinite;
						if (typeof t == "number") {
							if (t === 0) return l.__zero();
							if ((0 | t) === t) return 0 > t ? l.__oneDigit(-t, !0) : l.__oneDigit(t, !1);
							if (!r(t) || n(t) !== t) throw RangeError("The number " + t + " cannot be converted to BigInt because it is not an integer");
							return l.__fromDouble(t);
						}
						if (typeof t == "string") {
							var i = l.__fromString(t);
							if (i === null) throw SyntaxError("Cannot convert " + t + " to a BigInt");
							return i;
						}
						if (typeof t == "boolean") return !0 === t ? l.__oneDigit(1, !1) : l.__zero();
						if (e(t) === "object") {
							if (t.constructor === l) return t;
							var a = l.__toPrimitive(t);
							return l.BigInt(a);
						}
						throw TypeError("Cannot convert " + t + " to a BigInt");
					}
				},
				{
					key: "toNumber",
					value: function(e) {
						var t = e.length;
						if (t === 0) return 0;
						if (t === 1) {
							var n = e.__unsignedDigit(0);
							return e.sign ? -n : n;
						}
						var r = e.__digit(t - 1), i = c(r), a = 32 * t - i;
						if (1024 < a) return e.sign ? -Infinity : Infinity;
						var o = a - 1, s = r, u = t - 1, d = i + 1, f = d === 32 ? 0 : s << d;
						f >>>= 12;
						var p = d - 12, m = 12 <= d ? 0 : s << 20 + d, h = 20 + d;
						0 < p && 0 < u && (u--, s = e.__digit(u), f |= s >>> 32 - p, m = s << p, h = p), 0 < h && 0 < u && (u--, s = e.__digit(u), m |= s >>> 32 - h, h -= 32);
						var g = l.__decideRounding(e, h, u, s);
						if ((g === 1 || g === 0 && (1 & m) == 1) && (m = m + 1 >>> 0, m === 0 && (f++, f >>> 20 && (f = 0, o++, 1023 < o)))) return e.sign ? -Infinity : Infinity;
						var _ = e.sign ? -2147483648 : 0;
						return o = o + 1023 << 20, l.__kBitConversionInts[1] = _ | o | f, l.__kBitConversionInts[0] = m, l.__kBitConversionDouble[0];
					}
				},
				{
					key: "unaryMinus",
					value: function(e) {
						if (e.length === 0) return e;
						var t = e.__copy();
						return t.sign = !e.sign, t;
					}
				},
				{
					key: "bitwiseNot",
					value: function(e) {
						return e.sign ? l.__absoluteSubOne(e).__trim() : l.__absoluteAddOne(e, !0);
					}
				},
				{
					key: "exponentiate",
					value: function(e, t) {
						if (t.sign) throw RangeError("Exponent must be positive");
						if (t.length === 0) return l.__oneDigit(1, !1);
						if (e.length === 0) return e;
						if (e.length === 1 && e.__digit(0) === 1) return e.sign && !(1 & t.__digit(0)) ? l.unaryMinus(e) : e;
						if (1 < t.length) throw RangeError("BigInt too big");
						var n = t.__unsignedDigit(0);
						if (n === 1) return e;
						if (n >= l.__kMaxLengthBits) throw RangeError("BigInt too big");
						if (e.length === 1 && e.__digit(0) === 2) {
							var r = 1 + (n >>> 5), i = new l(r, e.sign && (1 & n) != 0);
							i.__initializeDigits();
							var a = 1 << (31 & n);
							return i.__setDigit(r - 1, a), i;
						}
						var o = null, s = e;
						for (1 & n && (o = e), n >>= 1; n !== 0; n >>= 1) s = l.multiply(s, s), 1 & n && (o = o === null ? s : l.multiply(o, s));
						return o;
					}
				},
				{
					key: "multiply",
					value: function(e, t) {
						if (e.length === 0) return e;
						if (t.length === 0) return t;
						var n = e.length + t.length;
						32 <= e.__clzmsd() + t.__clzmsd() && n--;
						var r = new l(n, e.sign !== t.sign);
						r.__initializeDigits();
						for (var i = 0; i < e.length; i++) l.__multiplyAccumulate(t, e.__digit(i), r, i);
						return r.__trim();
					}
				},
				{
					key: "divide",
					value: function(e, t) {
						if (t.length === 0) throw RangeError("Division by zero");
						if (0 > l.__absoluteCompare(e, t)) return l.__zero();
						var n, r = e.sign !== t.sign, i = t.__unsignedDigit(0);
						if (t.length === 1 && 65535 >= i) {
							if (i === 1) return r === e.sign ? e : l.unaryMinus(e);
							n = l.__absoluteDivSmall(e, i, null);
						} else n = l.__absoluteDivLarge(e, t, !0, !1);
						return n.sign = r, n.__trim();
					}
				},
				{
					key: "remainder",
					value: function(e, t) {
						if (t.length === 0) throw RangeError("Division by zero");
						if (0 > l.__absoluteCompare(e, t)) return e;
						var n = t.__unsignedDigit(0);
						if (t.length === 1 && 65535 >= n) {
							if (n === 1) return l.__zero();
							var r = l.__absoluteModSmall(e, n);
							return r === 0 ? l.__zero() : l.__oneDigit(r, e.sign);
						}
						var i = l.__absoluteDivLarge(e, t, !1, !0);
						return i.sign = e.sign, i.__trim();
					}
				},
				{
					key: "add",
					value: function(e, t) {
						var n = e.sign;
						return n === t.sign ? l.__absoluteAdd(e, t, n) : 0 <= l.__absoluteCompare(e, t) ? l.__absoluteSub(e, t, n) : l.__absoluteSub(t, e, !n);
					}
				},
				{
					key: "subtract",
					value: function(e, t) {
						var n = e.sign;
						return n === t.sign ? 0 <= l.__absoluteCompare(e, t) ? l.__absoluteSub(e, t, n) : l.__absoluteSub(t, e, !n) : l.__absoluteAdd(e, t, n);
					}
				},
				{
					key: "leftShift",
					value: function(e, t) {
						return t.length === 0 || e.length === 0 ? e : t.sign ? l.__rightShiftByAbsolute(e, t) : l.__leftShiftByAbsolute(e, t);
					}
				},
				{
					key: "signedRightShift",
					value: function(e, t) {
						return t.length === 0 || e.length === 0 ? e : t.sign ? l.__leftShiftByAbsolute(e, t) : l.__rightShiftByAbsolute(e, t);
					}
				},
				{
					key: "unsignedRightShift",
					value: function() {
						throw TypeError("BigInts have no unsigned right shift; use >> instead");
					}
				},
				{
					key: "lessThan",
					value: function(e, t) {
						return 0 > l.__compareToBigInt(e, t);
					}
				},
				{
					key: "lessThanOrEqual",
					value: function(e, t) {
						return 0 >= l.__compareToBigInt(e, t);
					}
				},
				{
					key: "greaterThan",
					value: function(e, t) {
						return 0 < l.__compareToBigInt(e, t);
					}
				},
				{
					key: "greaterThanOrEqual",
					value: function(e, t) {
						return 0 <= l.__compareToBigInt(e, t);
					}
				},
				{
					key: "equal",
					value: function(e, t) {
						if (e.sign !== t.sign || e.length !== t.length) return !1;
						for (var n = 0; n < e.length; n++) if (e.__digit(n) !== t.__digit(n)) return !1;
						return !0;
					}
				},
				{
					key: "notEqual",
					value: function(e, t) {
						return !l.equal(e, t);
					}
				},
				{
					key: "bitwiseAnd",
					value: function(e, t) {
						if (!e.sign && !t.sign) return l.__absoluteAnd(e, t).__trim();
						if (e.sign && t.sign) {
							var n = o(e.length, t.length) + 1, r = l.__absoluteSubOne(e, n), i = l.__absoluteSubOne(t);
							return r = l.__absoluteOr(r, i, r), l.__absoluteAddOne(r, !0, r).__trim();
						}
						if (e.sign) {
							var a = [t, e];
							e = a[0], t = a[1];
						}
						return l.__absoluteAndNot(e, l.__absoluteSubOne(t)).__trim();
					}
				},
				{
					key: "bitwiseXor",
					value: function(e, t) {
						if (!e.sign && !t.sign) return l.__absoluteXor(e, t).__trim();
						if (e.sign && t.sign) {
							var n = o(e.length, t.length), r = l.__absoluteSubOne(e, n), i = l.__absoluteSubOne(t);
							return l.__absoluteXor(r, i, r).__trim();
						}
						var a = o(e.length, t.length) + 1;
						if (e.sign) {
							var s = [t, e];
							e = s[0], t = s[1];
						}
						var c = l.__absoluteSubOne(t, a);
						return c = l.__absoluteXor(c, e, c), l.__absoluteAddOne(c, !0, c).__trim();
					}
				},
				{
					key: "bitwiseOr",
					value: function(e, t) {
						var n = o(e.length, t.length);
						if (!e.sign && !t.sign) return l.__absoluteOr(e, t).__trim();
						if (e.sign && t.sign) {
							var r = l.__absoluteSubOne(e, n), i = l.__absoluteSubOne(t);
							return r = l.__absoluteAnd(r, i, r), l.__absoluteAddOne(r, !0, r).__trim();
						}
						if (e.sign) {
							var a = [t, e];
							e = a[0], t = a[1];
						}
						var s = l.__absoluteSubOne(t, n);
						return s = l.__absoluteAndNot(s, e, s), l.__absoluteAddOne(s, !0, s).__trim();
					}
				},
				{
					key: "asIntN",
					value: function(e, t) {
						if (t.length === 0) return t;
						if (e === 0) return l.__zero();
						if (e >= l.__kMaxLengthBits) return t;
						var n = e + 31 >>> 5;
						if (t.length < n) return t;
						var r = t.__unsignedDigit(n - 1), i = 1 << (31 & e - 1);
						if (t.length === n && r < i) return t;
						if ((r & i) !== i) return l.__truncateToNBits(e, t);
						if (!t.sign) return l.__truncateAndSubFromPowerOfTwo(e, t, !0);
						if (!(r & i - 1)) {
							for (var a = n - 2; 0 <= a; a--) if (t.__digit(a) !== 0) return l.__truncateAndSubFromPowerOfTwo(e, t, !1);
							return t.length === n && r === i ? t : l.__truncateToNBits(e, t);
						}
						return l.__truncateAndSubFromPowerOfTwo(e, t, !1);
					}
				},
				{
					key: "asUintN",
					value: function(e, t) {
						if (t.length === 0) return t;
						if (e === 0) return l.__zero();
						if (t.sign) {
							if (e > l.__kMaxLengthBits) throw RangeError("BigInt too big");
							return l.__truncateAndSubFromPowerOfTwo(e, t, !1);
						}
						if (e >= l.__kMaxLengthBits) return t;
						var n = e + 31 >>> 5;
						if (t.length < n) return t;
						var r = 31 & e;
						return t.length == n && (r === 0 || !(t.__digit(n - 1) >>> r)) ? t : l.__truncateToNBits(e, t);
					}
				},
				{
					key: "ADD",
					value: function(e, t) {
						if (e = l.__toPrimitive(e), t = l.__toPrimitive(t), typeof e == "string") return typeof t != "string" && (t = t.toString()), e + t;
						if (typeof t == "string") return e.toString() + t;
						if (e = l.__toNumeric(e), t = l.__toNumeric(t), l.__isBigInt(e) && l.__isBigInt(t)) return l.add(e, t);
						if (typeof e == "number" && typeof t == "number") return e + t;
						throw TypeError("Cannot mix BigInt and other types, use explicit conversions");
					}
				},
				{
					key: "LT",
					value: function(e, t) {
						return l.__compare(e, t, 0);
					}
				},
				{
					key: "LE",
					value: function(e, t) {
						return l.__compare(e, t, 1);
					}
				},
				{
					key: "GT",
					value: function(e, t) {
						return l.__compare(e, t, 2);
					}
				},
				{
					key: "GE",
					value: function(e, t) {
						return l.__compare(e, t, 3);
					}
				},
				{
					key: "EQ",
					value: function(t, n) {
						for (;;) {
							if (l.__isBigInt(t)) return l.__isBigInt(n) ? l.equal(t, n) : l.EQ(n, t);
							if (typeof t == "number") {
								if (l.__isBigInt(n)) return l.__equalToNumber(n, t);
								if (e(n) !== "object") return t == n;
								n = l.__toPrimitive(n);
							} else if (typeof t == "string") {
								if (l.__isBigInt(n)) return t = l.__fromString(t), t !== null && l.equal(t, n);
								if (e(n) !== "object") return t == n;
								n = l.__toPrimitive(n);
							} else if (typeof t == "boolean") {
								if (l.__isBigInt(n)) return l.__equalToNumber(n, +t);
								if (e(n) !== "object") return t == n;
								n = l.__toPrimitive(n);
							} else if (e(t) === "symbol") {
								if (l.__isBigInt(n)) return !1;
								if (e(n) !== "object") return t == n;
								n = l.__toPrimitive(n);
							} else if (e(t) === "object") {
								if (e(n) === "object" && n.constructor !== l) return t == n;
								t = l.__toPrimitive(t);
							} else return t == n;
						}
					}
				},
				{
					key: "NE",
					value: function(e, t) {
						return !l.EQ(e, t);
					}
				},
				{
					key: "__zero",
					value: function() {
						return new l(0, !1);
					}
				},
				{
					key: "__oneDigit",
					value: function(e, t) {
						var n = new l(1, t);
						return n.__setDigit(0, e), n;
					}
				},
				{
					key: "__decideRounding",
					value: function(e, t, n, r) {
						if (0 < t) return -1;
						var i;
						if (0 > t) i = -t - 1;
						else {
							if (n === 0) return -1;
							n--, r = e.__digit(n), i = 31;
						}
						var a = 1 << i;
						if ((r & a) == 0) return -1;
						if (--a, (r & a) != 0) return 1;
						for (; 0 < n;) if (n--, e.__digit(n) !== 0) return 1;
						return 0;
					}
				},
				{
					key: "__fromDouble",
					value: function(e) {
						l.__kBitConversionDouble[0] = e;
						var t, n = (2047 & l.__kBitConversionInts[1] >>> 20) - 1023, r = (n >>> 5) + 1, i = new l(r, 0 > e), a = 1048575 & l.__kBitConversionInts[1] | 1048576, o = l.__kBitConversionInts[0], s = 20, c = 31 & n, u = 0;
						if (c < s) {
							var d = s - c;
							u = d + 32, t = a >>> d, a = a << 32 - d | o >>> d, o <<= 32 - d;
						} else if (c === s) u = 32, t = a, a = o;
						else {
							var f = c - s;
							u = 32 - f, t = a << f | o >>> 32 - f, a = o << f;
						}
						i.__setDigit(r - 1, t);
						for (var p = r - 2; 0 <= p; p--) 0 < u ? (u -= 32, t = a, a = o) : t = 0, i.__setDigit(p, t);
						return i.__trim();
					}
				},
				{
					key: "__isWhitespace",
					value: function(e) {
						return 13 >= e && 9 <= e || (159 >= e ? e == 32 : 131071 >= e ? e == 160 || e == 5760 : 196607 >= e ? (e &= 131071, 10 >= e || e == 40 || e == 41 || e == 47 || e == 95 || e == 4096) : e == 65279);
					}
				},
				{
					key: "__fromString",
					value: function(e) {
						var t = 1 < arguments.length && arguments[1] !== void 0 ? arguments[1] : 0, n = 0, r = e.length, i = 0;
						if (i === r) return l.__zero();
						for (var a = e.charCodeAt(i); l.__isWhitespace(a);) {
							if (++i === r) return l.__zero();
							a = e.charCodeAt(i);
						}
						if (a === 43) {
							if (++i === r) return null;
							a = e.charCodeAt(i), n = 1;
						} else if (a === 45) {
							if (++i === r) return null;
							a = e.charCodeAt(i), n = -1;
						}
						if (t === 0) {
							if (t = 10, a === 48) {
								if (++i === r) return l.__zero();
								if (a = e.charCodeAt(i), a === 88 || a === 120) {
									if (t = 16, ++i === r) return null;
									a = e.charCodeAt(i);
								} else if (a === 79 || a === 111) {
									if (t = 8, ++i === r) return null;
									a = e.charCodeAt(i);
								} else if (a === 66 || a === 98) {
									if (t = 2, ++i === r) return null;
									a = e.charCodeAt(i);
								}
							}
						} else if (t === 16 && a === 48) {
							if (++i === r) return l.__zero();
							if (a = e.charCodeAt(i), a === 88 || a === 120) {
								if (++i === r) return null;
								a = e.charCodeAt(i);
							}
						}
						for (; a === 48;) {
							if (++i === r) return l.__zero();
							a = e.charCodeAt(i);
						}
						var o = r - i, s = l.__kMaxBitsPerChar[t], c = l.__kBitsPerCharTableMultiplier - 1;
						if (o > 1073741824 / s) return null;
						var u = new l((s * o + c >>> l.__kBitsPerCharTableShift) + 31 >>> 5, !1), d = 10 > t ? t : 10, f = 10 < t ? t - 10 : 0;
						if (t & t - 1) {
							u.__initializeDigits();
							var p = !1, m = 0;
							do {
								for (var h, g = 0, _ = 1;;) {
									if (h = void 0, a - 48 >>> 0 < d) h = a - 48;
									else if ((32 | a) - 97 >>> 0 < f) h = (32 | a) - 87;
									else {
										p = !0;
										break;
									}
									var v = _ * t;
									if (4294967295 < v) break;
									if (_ = v, g = g * t + h, m++, ++i === r) {
										p = !0;
										break;
									}
									a = e.charCodeAt(i);
								}
								c = 32 * l.__kBitsPerCharTableMultiplier - 1;
								var y = s * m + c >>> l.__kBitsPerCharTableShift + 5;
								u.__inplaceMultiplyAdd(_, g, y);
							} while (!p);
						} else {
							s >>= l.__kBitsPerCharTableShift;
							var b = [], x = [], S = !1;
							do {
								for (var C, w = 0, T = 0;;) {
									if (C = void 0, a - 48 >>> 0 < d) C = a - 48;
									else if ((32 | a) - 97 >>> 0 < f) C = (32 | a) - 87;
									else {
										S = !0;
										break;
									}
									if (T += s, w = w << s | C, ++i === r) {
										S = !0;
										break;
									}
									if (a = e.charCodeAt(i), 32 < T + s) break;
								}
								b.push(w), x.push(T);
							} while (!S);
							l.__fillFromParts(u, b, x);
						}
						if (i !== r) {
							if (!l.__isWhitespace(a)) return null;
							for (i++; i < r; i++) if (a = e.charCodeAt(i), !l.__isWhitespace(a)) return null;
						}
						return n !== 0 && t !== 10 ? null : (u.sign = n === -1, u.__trim());
					}
				},
				{
					key: "__fillFromParts",
					value: function(e, t, n) {
						for (var r = 0, i = 0, a = 0, o = t.length - 1; 0 <= o; o--) {
							var s = t[o], c = n[o];
							i |= s << a, a += c, a === 32 ? (e.__setDigit(r++, i), a = 0, i = 0) : 32 < a && (e.__setDigit(r++, i), a -= 32, i = s >>> c - a);
						}
						if (i !== 0) {
							if (r >= e.length) throw Error("implementation bug");
							e.__setDigit(r++, i);
						}
						for (; r < e.length; r++) e.__setDigit(r, 0);
					}
				},
				{
					key: "__toStringBasePowerOfTwo",
					value: function(e, t) {
						var n = e.length, r = t - 1;
						r = (85 & r >>> 1) + (85 & r), r = (51 & r >>> 2) + (51 & r), r = (15 & r >>> 4) + (15 & r);
						var i = r, a = t - 1, o = e.__digit(n - 1), s = c(o), u = 0 | (32 * n - s + i - 1) / i;
						if (e.sign && u++, 268435456 < u) throw Error("string too long");
						for (var d = Array(u), f = u - 1, p = 0, m = 0, h = 0; h < n - 1; h++) {
							var g = e.__digit(h), _ = (p | g << m) & a;
							d[f--] = l.__kConversionChars[_];
							var v = i - m;
							for (p = g >>> v, m = 32 - v; m >= i;) d[f--] = l.__kConversionChars[p & a], p >>>= i, m -= i;
						}
						var y = (p | o << m) & a;
						for (d[f--] = l.__kConversionChars[y], p = o >>> i - m; p !== 0;) d[f--] = l.__kConversionChars[p & a], p >>>= i;
						if (e.sign && (d[f--] = "-"), f !== -1) throw Error("implementation bug");
						return d.join("");
					}
				},
				{
					key: "__toStringGeneric",
					value: function(e, t, n) {
						var r = e.length;
						if (r === 0) return "";
						if (r === 1) {
							var i = e.__unsignedDigit(0).toString(t);
							return !1 === n && e.sign && (i = "-" + i), i;
						}
						var a = 32 * r - c(e.__digit(r - 1)), o = l.__kMaxBitsPerChar[t] - 1, s = a * l.__kBitsPerCharTableMultiplier;
						s += o - 1, s = 0 | s / o;
						var u, d, f = s + 1 >> 1, p = l.exponentiate(l.__oneDigit(t, !1), l.__oneDigit(f, !1)), m = p.__unsignedDigit(0);
						if (p.length === 1 && 65535 >= m) {
							u = new l(e.length, !1), u.__initializeDigits();
							for (var h, g = 0, _ = 2 * e.length - 1; 0 <= _; _--) h = g << 16 | e.__halfDigit(_), u.__setHalfDigit(_, 0 | h / m), g = 0 | h % m;
							d = g.toString(t);
						} else {
							var v = l.__absoluteDivLarge(e, p, !0, !0);
							u = v.quotient;
							var y = v.remainder.__trim();
							d = l.__toStringGeneric(y, t, !0);
						}
						u.__trim();
						for (var b = l.__toStringGeneric(u, t, !0); d.length < f;) d = "0" + d;
						return !1 === n && e.sign && (b = "-" + b), b + d;
					}
				},
				{
					key: "__unequalSign",
					value: function(e) {
						return e ? -1 : 1;
					}
				},
				{
					key: "__absoluteGreater",
					value: function(e) {
						return e ? -1 : 1;
					}
				},
				{
					key: "__absoluteLess",
					value: function(e) {
						return e ? 1 : -1;
					}
				},
				{
					key: "__compareToBigInt",
					value: function(e, t) {
						var n = e.sign;
						if (n !== t.sign) return l.__unequalSign(n);
						var r = l.__absoluteCompare(e, t);
						return 0 < r ? l.__absoluteGreater(n) : 0 > r ? l.__absoluteLess(n) : 0;
					}
				},
				{
					key: "__compareToNumber",
					value: function(e, t) {
						if (!0 | t) {
							var n = e.sign, r = 0 > t;
							if (n !== r) return l.__unequalSign(n);
							if (e.length === 0) {
								if (r) throw Error("implementation bug");
								return t === 0 ? 0 : -1;
							}
							if (1 < e.length) return l.__absoluteGreater(n);
							var i = a(t), o = e.__unsignedDigit(0);
							return o > i ? l.__absoluteGreater(n) : o < i ? l.__absoluteLess(n) : 0;
						}
						return l.__compareToDouble(e, t);
					}
				},
				{
					key: "__compareToDouble",
					value: function(e, t) {
						if (t !== t) return t;
						if (t === Infinity) return -1;
						if (t === -Infinity) return 1;
						var n = e.sign;
						if (n !== 0 > t) return l.__unequalSign(n);
						if (t === 0) throw Error("implementation bug: should be handled elsewhere");
						if (e.length === 0) return -1;
						l.__kBitConversionDouble[0] = t;
						var r = 2047 & l.__kBitConversionInts[1] >>> 20;
						if (r == 2047) throw Error("implementation bug: handled elsewhere");
						var i = r - 1023;
						if (0 > i) return l.__absoluteGreater(n);
						var a = e.length, o = e.__digit(a - 1), s = c(o), u = 32 * a - s, d = i + 1;
						if (u < d) return l.__absoluteLess(n);
						if (u > d) return l.__absoluteGreater(n);
						var f = 1048576 | 1048575 & l.__kBitConversionInts[1], p = l.__kBitConversionInts[0], m = 20, h = 31 - s;
						if (h !== (u - 1) % 31) throw Error("implementation bug");
						var g, _ = 0;
						if (h < m) {
							var v = m - h;
							_ = v + 32, g = f >>> v, f = f << 32 - v | p >>> v, p <<= 32 - v;
						} else if (h === m) _ = 32, g = f, f = p;
						else {
							var y = h - m;
							_ = 32 - y, g = f << y | p >>> 32 - y, f = p << y;
						}
						if (o >>>= 0, g >>>= 0, o > g) return l.__absoluteGreater(n);
						if (o < g) return l.__absoluteLess(n);
						for (var b = a - 2; 0 <= b; b--) {
							0 < _ ? (_ -= 32, g = f >>> 0, f = p, p = 0) : g = 0;
							var x = e.__unsignedDigit(b);
							if (x > g) return l.__absoluteGreater(n);
							if (x < g) return l.__absoluteLess(n);
						}
						if (f !== 0 || p !== 0) {
							if (_ === 0) throw Error("implementation bug");
							return l.__absoluteLess(n);
						}
						return 0;
					}
				},
				{
					key: "__equalToNumber",
					value: function(e, t) {
						return t | t === 0 ? t === 0 ? e.length === 0 : e.length === 1 && e.sign === 0 > t && e.__unsignedDigit(0) === a(t) : l.__compareToDouble(e, t) === 0;
					}
				},
				{
					key: "__comparisonResultToBool",
					value: function(e, t) {
						switch (t) {
							case 0: return 0 > e;
							case 1: return 0 >= e;
							case 2: return 0 < e;
							case 3: return 0 <= e;
						}
						throw Error("unreachable");
					}
				},
				{
					key: "__compare",
					value: function(e, t, n) {
						if (e = l.__toPrimitive(e), t = l.__toPrimitive(t), typeof e == "string" && typeof t == "string") switch (n) {
							case 0: return e < t;
							case 1: return e <= t;
							case 2: return e > t;
							case 3: return e >= t;
						}
						if (l.__isBigInt(e) && typeof t == "string") return t = l.__fromString(t), t !== null && l.__comparisonResultToBool(l.__compareToBigInt(e, t), n);
						if (typeof e == "string" && l.__isBigInt(t)) return e = l.__fromString(e), e !== null && l.__comparisonResultToBool(l.__compareToBigInt(e, t), n);
						if (e = l.__toNumeric(e), t = l.__toNumeric(t), l.__isBigInt(e)) {
							if (l.__isBigInt(t)) return l.__comparisonResultToBool(l.__compareToBigInt(e, t), n);
							if (typeof t != "number") throw Error("implementation bug");
							return l.__comparisonResultToBool(l.__compareToNumber(e, t), n);
						}
						if (typeof e != "number") throw Error("implementation bug");
						if (l.__isBigInt(t)) return l.__comparisonResultToBool(l.__compareToNumber(t, e), 2 ^ n);
						if (typeof t != "number") throw Error("implementation bug");
						return n === 0 ? e < t : n === 1 ? e <= t : n === 2 ? e > t : n === 3 ? e >= t : void 0;
					}
				},
				{
					key: "__absoluteAdd",
					value: function(e, t, n) {
						if (e.length < t.length) return l.__absoluteAdd(t, e, n);
						if (e.length === 0) return e;
						if (t.length === 0) return e.sign === n ? e : l.unaryMinus(e);
						var r = e.length;
						(e.__clzmsd() === 0 || t.length === e.length && t.__clzmsd() === 0) && r++;
						for (var i = new l(r, n), a = 0, o = 0; o < t.length; o++) {
							var s = t.__digit(o), c = e.__digit(o), u = (65535 & c) + (65535 & s) + a, d = (c >>> 16) + (s >>> 16) + (u >>> 16);
							a = d >>> 16, i.__setDigit(o, 65535 & u | d << 16);
						}
						for (; o < e.length; o++) {
							var f = e.__digit(o), p = (65535 & f) + a, m = (f >>> 16) + (p >>> 16);
							a = m >>> 16, i.__setDigit(o, 65535 & p | m << 16);
						}
						return o < i.length && i.__setDigit(o, a), i.__trim();
					}
				},
				{
					key: "__absoluteSub",
					value: function(e, t, n) {
						if (e.length === 0) return e;
						if (t.length === 0) return e.sign === n ? e : l.unaryMinus(e);
						for (var r = new l(e.length, n), i = 0, a = 0; a < t.length; a++) {
							var o = e.__digit(a), s = t.__digit(a), c = (65535 & o) - (65535 & s) - i;
							i = 1 & c >>> 16;
							var u = (o >>> 16) - (s >>> 16) - i;
							i = 1 & u >>> 16, r.__setDigit(a, 65535 & c | u << 16);
						}
						for (; a < e.length; a++) {
							var d = e.__digit(a), f = (65535 & d) - i;
							i = 1 & f >>> 16;
							var p = (d >>> 16) - i;
							i = 1 & p >>> 16, r.__setDigit(a, 65535 & f | p << 16);
						}
						return r.__trim();
					}
				},
				{
					key: "__absoluteAddOne",
					value: function(e, t) {
						var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null, r = e.length;
						n === null ? n = new l(r, t) : n.sign = t;
						for (var i, a = !0, o = 0; o < r; o++) {
							if (i = e.__digit(o), a) {
								var s = i === -1;
								i = 0 | i + 1, a = s;
							}
							n.__setDigit(o, i);
						}
						return a && n.__setDigitGrow(r, 1), n;
					}
				},
				{
					key: "__absoluteSubOne",
					value: function(e, t) {
						var n = e.length;
						t ||= n;
						for (var r, i = new l(t, !1), a = !0, o = 0; o < n; o++) {
							if (r = e.__digit(o), a) {
								var s = r === 0;
								r = 0 | r - 1, a = s;
							}
							i.__setDigit(o, r);
						}
						if (a) throw Error("implementation bug");
						for (var c = n; c < t; c++) i.__setDigit(c, 0);
						return i;
					}
				},
				{
					key: "__absoluteAnd",
					value: function(e, t) {
						var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null, r = e.length, i = t.length, a = i;
						if (r < i) {
							a = r;
							var o = e, s = r;
							e = t, r = i, t = o, i = s;
						}
						var c = a;
						n === null ? n = new l(c, !1) : c = n.length;
						for (var u = 0; u < a; u++) n.__setDigit(u, e.__digit(u) & t.__digit(u));
						for (; u < c; u++) n.__setDigit(u, 0);
						return n;
					}
				},
				{
					key: "__absoluteAndNot",
					value: function(e, t) {
						var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null, r = e.length, i = t.length, a = i;
						r < i && (a = r);
						var o = r;
						n === null ? n = new l(o, !1) : o = n.length;
						for (var s = 0; s < a; s++) n.__setDigit(s, e.__digit(s) & ~t.__digit(s));
						for (; s < r; s++) n.__setDigit(s, e.__digit(s));
						for (; s < o; s++) n.__setDigit(s, 0);
						return n;
					}
				},
				{
					key: "__absoluteOr",
					value: function(e, t) {
						var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null, r = e.length, i = t.length, a = i;
						if (r < i) {
							a = r;
							var o = e, s = r;
							e = t, r = i, t = o, i = s;
						}
						var c = r;
						n === null ? n = new l(c, !1) : c = n.length;
						for (var u = 0; u < a; u++) n.__setDigit(u, e.__digit(u) | t.__digit(u));
						for (; u < r; u++) n.__setDigit(u, e.__digit(u));
						for (; u < c; u++) n.__setDigit(u, 0);
						return n;
					}
				},
				{
					key: "__absoluteXor",
					value: function(e, t) {
						var n = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null, r = e.length, i = t.length, a = i;
						if (r < i) {
							a = r;
							var o = e, s = r;
							e = t, r = i, t = o, i = s;
						}
						var c = r;
						n === null ? n = new l(c, !1) : c = n.length;
						for (var u = 0; u < a; u++) n.__setDigit(u, e.__digit(u) ^ t.__digit(u));
						for (; u < r; u++) n.__setDigit(u, e.__digit(u));
						for (; u < c; u++) n.__setDigit(u, 0);
						return n;
					}
				},
				{
					key: "__absoluteCompare",
					value: function(e, t) {
						var n = e.length - t.length;
						if (n != 0) return n;
						for (var r = e.length - 1; 0 <= r && e.__digit(r) === t.__digit(r);) r--;
						return 0 > r ? 0 : e.__unsignedDigit(r) > t.__unsignedDigit(r) ? 1 : -1;
					}
				},
				{
					key: "__multiplyAccumulate",
					value: function(e, t, n, r) {
						if (t !== 0) {
							for (var i = 65535 & t, a = t >>> 16, o = 0, c = 0, l = 0, u = 0; u < e.length; u++, r++) {
								var d = n.__digit(r), f = 65535 & d, p = d >>> 16, m = e.__digit(u), h = 65535 & m, g = m >>> 16, _ = s(h, i), v = s(h, a), y = s(g, i), b = s(g, a);
								f += c + (65535 & _), p += l + o + (f >>> 16) + (_ >>> 16) + (65535 & v) + (65535 & y), o = p >>> 16, c = (v >>> 16) + (y >>> 16) + (65535 & b) + o, o = c >>> 16, c &= 65535, l = b >>> 16, d = 65535 & f | p << 16, n.__setDigit(r, d);
							}
							for (; o !== 0 || c !== 0 || l !== 0; r++) {
								var x = n.__digit(r), S = (65535 & x) + c, C = (x >>> 16) + (S >>> 16) + l + o;
								c = 0, l = 0, o = C >>> 16, x = 65535 & S | C << 16, n.__setDigit(r, x);
							}
						}
					}
				},
				{
					key: "__internalMultiplyAdd",
					value: function(e, t, n, r, i) {
						for (var a = n, o = 0, c = 0; c < r; c++) {
							var l = e.__digit(c), u = s(65535 & l, t), d = (65535 & u) + o + a;
							a = d >>> 16;
							var f = s(l >>> 16, t), p = (65535 & f) + (u >>> 16) + a;
							a = p >>> 16, o = f >>> 16, i.__setDigit(c, p << 16 | 65535 & d);
						}
						if (i.length > r) for (i.__setDigit(r++, a + o); r < i.length;) i.__setDigit(r++, 0);
						else if (a + o !== 0) throw Error("implementation bug");
					}
				},
				{
					key: "__absoluteDivSmall",
					value: function(e, t, n) {
						n === null && (n = new l(e.length, !1));
						for (var r = 0, i = 2 * e.length - 1; 0 <= i; i -= 2) {
							var a = (r << 16 | e.__halfDigit(i)) >>> 0, o = 0 | a / t;
							r = 0 | a % t, a = (r << 16 | e.__halfDigit(i - 1)) >>> 0;
							var s = 0 | a / t;
							r = 0 | a % t, n.__setDigit(i >>> 1, o << 16 | s);
						}
						return n;
					}
				},
				{
					key: "__absoluteModSmall",
					value: function(e, t) {
						for (var n, r = 0, i = 2 * e.length - 1; 0 <= i; i--) n = (r << 16 | e.__halfDigit(i)) >>> 0, r = 0 | n % t;
						return r;
					}
				},
				{
					key: "__absoluteDivLarge",
					value: function(e, t, n, r) {
						var i = t.__halfDigitLength(), a = t.length, o = e.__halfDigitLength() - i, c = null;
						n && (c = new l(o + 2 >>> 1, !1), c.__initializeDigits());
						var u = new l(i + 2 >>> 1, !1);
						u.__initializeDigits();
						var d = l.__clz16(t.__halfDigit(i - 1));
						0 < d && (t = l.__specialLeftShift(t, d, 0));
						for (var f = l.__specialLeftShift(e, d, 1), p = t.__halfDigit(i - 1), m = 0, h = o; 0 <= h; h--) {
							var g = 65535, _ = f.__halfDigit(h + i);
							if (_ !== p) {
								var v = (_ << 16 | f.__halfDigit(h + i - 1)) >>> 0;
								g = 0 | v / p;
								for (var y = 0 | v % p, b = t.__halfDigit(i - 2), x = f.__halfDigit(h + i - 2); s(g, b) >>> 0 > (y << 16 | x) >>> 0 && (g--, y += p, !(65535 < y)););
							}
							l.__internalMultiplyAdd(t, g, 0, a, u);
							var S = f.__inplaceSub(u, h, i + 1);
							S !== 0 && (S = f.__inplaceAdd(t, h, i), f.__setHalfDigit(h + i, f.__halfDigit(h + i) + S), g--), n && (1 & h ? m = g << 16 : c.__setDigit(h >>> 1, m | g));
						}
						return r ? (f.__inplaceRightShift(d), n ? {
							quotient: c,
							remainder: f
						} : f) : n ? c : void 0;
					}
				},
				{
					key: "__clz16",
					value: function(e) {
						return c(e) - 16;
					}
				},
				{
					key: "__specialLeftShift",
					value: function(e, t, n) {
						var r = e.length, i = new l(r + n, !1);
						if (t === 0) {
							for (var a = 0; a < r; a++) i.__setDigit(a, e.__digit(a));
							return 0 < n && i.__setDigit(r, 0), i;
						}
						for (var o, s = 0, c = 0; c < r; c++) o = e.__digit(c), i.__setDigit(c, o << t | s), s = o >>> 32 - t;
						return 0 < n && i.__setDigit(r, s), i;
					}
				},
				{
					key: "__leftShiftByAbsolute",
					value: function(e, t) {
						var n = l.__toShiftAmount(t);
						if (0 > n) throw RangeError("BigInt too big");
						var r = n >>> 5, i = 31 & n, a = e.length, o = i !== 0 && e.__digit(a - 1) >>> 32 - i != 0, s = a + r + (o ? 1 : 0), c = new l(s, e.sign);
						if (i === 0) {
							for (var u = 0; u < r; u++) c.__setDigit(u, 0);
							for (; u < s; u++) c.__setDigit(u, e.__digit(u - r));
						} else {
							for (var d = 0, f = 0; f < r; f++) c.__setDigit(f, 0);
							for (var p, m = 0; m < a; m++) p = e.__digit(m), c.__setDigit(m + r, p << i | d), d = p >>> 32 - i;
							if (o) c.__setDigit(a + r, d);
							else if (d !== 0) throw Error("implementation bug");
						}
						return c.__trim();
					}
				},
				{
					key: "__rightShiftByAbsolute",
					value: function(e, t) {
						var n = e.length, r = e.sign, i = l.__toShiftAmount(t);
						if (0 > i) return l.__rightShiftByMaximum(r);
						var a = i >>> 5, o = 31 & i, s = n - a;
						if (0 >= s) return l.__rightShiftByMaximum(r);
						var c = !1;
						if (r) {
							if (e.__digit(a) & (1 << o) - 1) c = !0;
							else for (var u = 0; u < a; u++) if (e.__digit(u) !== 0) {
								c = !0;
								break;
							}
						}
						c && o === 0 && ~e.__digit(n - 1) == 0 && s++;
						var d = new l(s, r);
						if (o === 0) for (var f = a; f < n; f++) d.__setDigit(f - a, e.__digit(f));
						else {
							for (var p, m = e.__digit(a) >>> o, h = n - a - 1, g = 0; g < h; g++) p = e.__digit(g + a + 1), d.__setDigit(g, p << 32 - o | m), m = p >>> o;
							d.__setDigit(h, m);
						}
						return c && (d = l.__absoluteAddOne(d, !0, d)), d.__trim();
					}
				},
				{
					key: "__rightShiftByMaximum",
					value: function(e) {
						return e ? l.__oneDigit(1, !0) : l.__zero();
					}
				},
				{
					key: "__toShiftAmount",
					value: function(e) {
						if (1 < e.length) return -1;
						var t = e.__unsignedDigit(0);
						return t > l.__kMaxLengthBits ? -1 : t;
					}
				},
				{
					key: "__toPrimitive",
					value: function(t) {
						var n = 1 < arguments.length && arguments[1] !== void 0 ? arguments[1] : "default";
						if (e(t) !== "object" || t.constructor === l) return t;
						var r = t[Symbol.toPrimitive];
						if (r) {
							var i = r(n);
							if (e(i) !== "object") return i;
							throw TypeError("Cannot convert object to primitive value");
						}
						var a = t.valueOf;
						if (a) {
							var o = a.call(t);
							if (e(o) !== "object") return o;
						}
						var s = t.toString;
						if (s) {
							var c = s.call(t);
							if (e(c) !== "object") return c;
						}
						throw TypeError("Cannot convert object to primitive value");
					}
				},
				{
					key: "__toNumeric",
					value: function(e) {
						return l.__isBigInt(e) ? e : +e;
					}
				},
				{
					key: "__isBigInt",
					value: function(t) {
						return e(t) === "object" && t.constructor === l;
					}
				},
				{
					key: "__truncateToNBits",
					value: function(e, t) {
						for (var n = e + 31 >>> 5, r = new l(n, t.sign), i = n - 1, a = 0; a < i; a++) r.__setDigit(a, t.__digit(a));
						var o = t.__digit(i);
						if (31 & e) {
							var s = 32 - (31 & e);
							o = o << s >>> s;
						}
						return r.__setDigit(i, o), r.__trim();
					}
				},
				{
					key: "__truncateAndSubFromPowerOfTwo",
					value: function(e, t, n) {
						for (var r = Math.min, i = e + 31 >>> 5, a = new l(i, n), o = 0, s = i - 1, c = 0, u = r(s, t.length); o < u; o++) {
							var d = t.__digit(o), f = 0 - (65535 & d) - c;
							c = 1 & f >>> 16;
							var p = 0 - (d >>> 16) - c;
							c = 1 & p >>> 16, a.__setDigit(o, 65535 & f | p << 16);
						}
						for (; o < s; o++) a.__setDigit(o, 0 | -c);
						var m, h = s < t.length ? t.__digit(s) : 0, g = 31 & e;
						if (g === 0) {
							var _ = 0 - (65535 & h) - c;
							c = 1 & _ >>> 16;
							var v = 0 - (h >>> 16) - c;
							m = 65535 & _ | v << 16;
						} else {
							var y = 32 - g;
							h = h << y >>> y;
							var b = 1 << 32 - y, x = (65535 & b) - (65535 & h) - c;
							c = 1 & x >>> 16;
							var S = (b >>> 16) - (h >>> 16) - c;
							m = 65535 & x | S << 16, m &= b - 1;
						}
						return a.__setDigit(s, m), a.__trim();
					}
				},
				{
					key: "__digitPow",
					value: function(e, t) {
						for (var n = 1; 0 < t;) 1 & t && (n *= e), t >>>= 1, e *= e;
						return n;
					}
				}
			]), l;
		}(u(Array));
		return _.__kMaxLength = 33554432, _.__kMaxLengthBits = _.__kMaxLength << 5, _.__kMaxBitsPerChar = [
			0,
			0,
			32,
			51,
			64,
			75,
			83,
			90,
			96,
			102,
			107,
			111,
			115,
			119,
			122,
			126,
			128,
			131,
			134,
			136,
			139,
			141,
			143,
			145,
			147,
			149,
			151,
			153,
			154,
			156,
			158,
			159,
			160,
			162,
			163,
			165,
			166
		], _.__kBitsPerCharTableShift = 5, _.__kBitsPerCharTableMultiplier = 1 << _.__kBitsPerCharTableShift, _.__kConversionChars = /* @__PURE__ */ "0123456789abcdefghijklmnopqrstuvwxyz".split(""), _.__kBitConversionBuffer = /* @__PURE__ */ new ArrayBuffer(8), _.__kBitConversionDouble = new Float64Array(_.__kBitConversionBuffer), _.__kBitConversionInts = new Int32Array(_.__kBitConversionBuffer), _;
	});
})), Ko = /* @__PURE__ */ c({
	author: () => ts,
	bugs: () => ns,
	default: () => os,
	dependencies: () => as,
	description: () => Yo,
	devDependencies: () => is,
	files: () => Zo,
	homepage: () => rs,
	keywords: () => es,
	license: () => "MIT",
	main: () => Xo,
	name: () => qo,
	repository: () => $o,
	scripts: () => Qo,
	version: () => Jo
}), qo, Jo, Yo, Xo, Zo, Qo, $o, es, ts, ns, rs, is, as, os, ss = o((() => {
	qo = "elliptic", Jo = "6.6.1", Yo = "EC cryptography", Xo = "lib/elliptic.js", Zo = ["lib"], Qo = {
		lint: "eslint lib test",
		"lint:fix": "npm run lint -- --fix",
		unit: "istanbul test _mocha --reporter=spec test/index.js",
		test: "npm run lint && npm run unit",
		version: "grunt dist && git add dist/"
	}, $o = {
		type: "git",
		url: "git@github.com:indutny/elliptic"
	}, es = [
		"EC",
		"Elliptic",
		"curve",
		"Cryptography"
	], ts = "Fedor Indutny <fedor@indutny.com>", ns = { url: "https://github.com/indutny/elliptic/issues" }, rs = "https://github.com/indutny/elliptic", is = {
		brfs: "^2.0.2",
		coveralls: "^3.1.0",
		eslint: "^7.6.0",
		grunt: "^1.2.1",
		"grunt-browserify": "^5.3.0",
		"grunt-cli": "^1.3.2",
		"grunt-contrib-connect": "^3.0.0",
		"grunt-contrib-copy": "^1.0.0",
		"grunt-contrib-uglify": "^5.0.0",
		"grunt-mocha-istanbul": "^5.0.2",
		"grunt-saucelabs": "^9.0.1",
		istanbul: "^0.4.5",
		mocha: "^8.0.1"
	}, as = {
		"bn.js": "^4.11.9",
		brorand: "^1.1.0",
		"hash.js": "^1.0.0",
		"hmac-drbg": "^1.0.1",
		inherits: "^2.0.4",
		"minimalistic-assert": "^1.0.1",
		"minimalistic-crypto-utils": "^1.0.1"
	}, os = {
		name: qo,
		version: Jo,
		description: Yo,
		main: Xo,
		files: Zo,
		scripts: Qo,
		repository: $o,
		keywords: es,
		author: ts,
		license: "MIT",
		bugs: ns,
		homepage: rs,
		devDependencies: is,
		dependencies: as
	};
})), cs = /* @__PURE__ */ s(((e, t) => {
	t.exports = {};
})), ls = /* @__PURE__ */ s(((e, t) => {
	(function(e, t) {
		function n(e, t) {
			if (!e) throw Error(t || "Assertion failed");
		}
		function r(e, t) {
			e.super_ = t;
			var n = function() {};
			n.prototype = t.prototype, e.prototype = new n(), e.prototype.constructor = e;
		}
		function i(e, t, n) {
			if (i.isBN(e)) return e;
			this.negative = 0, this.words = null, this.length = 0, this.red = null, e !== null && ((t === "le" || t === "be") && (n = t, t = 10), this._init(e || 0, t || 10, n || "be"));
		}
		typeof e == "object" ? e.exports = i : t.BN = i, i.BN = i, i.wordSize = 26;
		var a;
		try {
			a = typeof window < "u" && window.Buffer !== void 0 ? window.Buffer : cs().Buffer;
		} catch {}
		i.isBN = function(e) {
			return e instanceof i ? !0 : typeof e == "object" && !!e && e.constructor.wordSize === i.wordSize && Array.isArray(e.words);
		}, i.max = function(e, t) {
			return e.cmp(t) > 0 ? e : t;
		}, i.min = function(e, t) {
			return e.cmp(t) < 0 ? e : t;
		}, i.prototype._init = function(e, t, r) {
			if (typeof e == "number") return this._initNumber(e, t, r);
			if (typeof e == "object") return this._initArray(e, t, r);
			t === "hex" && (t = 16), n(t === (t | 0) && t >= 2 && t <= 36), e = e.toString().replace(/\s+/g, "");
			var i = 0;
			e[0] === "-" && (i++, this.negative = 1), i < e.length && (t === 16 ? this._parseHex(e, i, r) : (this._parseBase(e, t, i), r === "le" && this._initArray(this.toArray(), t, r)));
		}, i.prototype._initNumber = function(e, t, r) {
			e < 0 && (this.negative = 1, e = -e), e < 67108864 ? (this.words = [e & 67108863], this.length = 1) : e < 4503599627370496 ? (this.words = [e & 67108863, e / 67108864 & 67108863], this.length = 2) : (n(e < 9007199254740992), this.words = [
				e & 67108863,
				e / 67108864 & 67108863,
				1
			], this.length = 3), r === "le" && this._initArray(this.toArray(), t, r);
		}, i.prototype._initArray = function(e, t, r) {
			if (n(typeof e.length == "number"), e.length <= 0) return this.words = [0], this.length = 1, this;
			this.length = Math.ceil(e.length / 3), this.words = Array(this.length);
			for (var i = 0; i < this.length; i++) this.words[i] = 0;
			var a, o, s = 0;
			if (r === "be") for (i = e.length - 1, a = 0; i >= 0; i -= 3) o = e[i] | e[i - 1] << 8 | e[i - 2] << 16, this.words[a] |= o << s & 67108863, this.words[a + 1] = o >>> 26 - s & 67108863, s += 24, s >= 26 && (s -= 26, a++);
			else if (r === "le") for (i = 0, a = 0; i < e.length; i += 3) o = e[i] | e[i + 1] << 8 | e[i + 2] << 16, this.words[a] |= o << s & 67108863, this.words[a + 1] = o >>> 26 - s & 67108863, s += 24, s >= 26 && (s -= 26, a++);
			return this.strip();
		};
		function o(e, t) {
			var n = e.charCodeAt(t);
			return n >= 65 && n <= 70 ? n - 55 : n >= 97 && n <= 102 ? n - 87 : n - 48 & 15;
		}
		function s(e, t, n) {
			var r = o(e, n);
			return n - 1 >= t && (r |= o(e, n - 1) << 4), r;
		}
		i.prototype._parseHex = function(e, t, n) {
			this.length = Math.ceil((e.length - t) / 6), this.words = Array(this.length);
			for (var r = 0; r < this.length; r++) this.words[r] = 0;
			var i = 0, a = 0, o;
			if (n === "be") for (r = e.length - 1; r >= t; r -= 2) o = s(e, t, r) << i, this.words[a] |= o & 67108863, i >= 18 ? (i -= 18, a += 1, this.words[a] |= o >>> 26) : i += 8;
			else for (r = (e.length - t) % 2 == 0 ? t + 1 : t; r < e.length; r += 2) o = s(e, t, r) << i, this.words[a] |= o & 67108863, i >= 18 ? (i -= 18, a += 1, this.words[a] |= o >>> 26) : i += 8;
			this.strip();
		};
		function c(e, t, n, r) {
			for (var i = 0, a = Math.min(e.length, n), o = t; o < a; o++) {
				var s = e.charCodeAt(o) - 48;
				i *= r, s >= 49 ? i += s - 49 + 10 : s >= 17 ? i += s - 17 + 10 : i += s;
			}
			return i;
		}
		i.prototype._parseBase = function(e, t, n) {
			this.words = [0], this.length = 1;
			for (var r = 0, i = 1; i <= 67108863; i *= t) r++;
			r--, i = i / t | 0;
			for (var a = e.length - n, o = a % r, s = Math.min(a, a - o) + n, l = 0, u = n; u < s; u += r) l = c(e, u, u + r, t), this.imuln(i), this.words[0] + l < 67108864 ? this.words[0] += l : this._iaddn(l);
			if (o !== 0) {
				var d = 1;
				for (l = c(e, u, e.length, t), u = 0; u < o; u++) d *= t;
				this.imuln(d), this.words[0] + l < 67108864 ? this.words[0] += l : this._iaddn(l);
			}
			this.strip();
		}, i.prototype.copy = function(e) {
			e.words = Array(this.length);
			for (var t = 0; t < this.length; t++) e.words[t] = this.words[t];
			e.length = this.length, e.negative = this.negative, e.red = this.red;
		}, i.prototype.clone = function() {
			var e = new i(null);
			return this.copy(e), e;
		}, i.prototype._expand = function(e) {
			for (; this.length < e;) this.words[this.length++] = 0;
			return this;
		}, i.prototype.strip = function() {
			for (; this.length > 1 && this.words[this.length - 1] === 0;) this.length--;
			return this._normSign();
		}, i.prototype._normSign = function() {
			return this.length === 1 && this.words[0] === 0 && (this.negative = 0), this;
		}, i.prototype.inspect = function() {
			return (this.red ? "<BN-R: " : "<BN: ") + this.toString(16) + ">";
		};
		var l = /* @__PURE__ */ ".0.00.000.0000.00000.000000.0000000.00000000.000000000.0000000000.00000000000.000000000000.0000000000000.00000000000000.000000000000000.0000000000000000.00000000000000000.000000000000000000.0000000000000000000.00000000000000000000.000000000000000000000.0000000000000000000000.00000000000000000000000.000000000000000000000000.0000000000000000000000000".split("."), u = [
			0,
			0,
			25,
			16,
			12,
			11,
			10,
			9,
			8,
			8,
			7,
			7,
			7,
			7,
			6,
			6,
			6,
			6,
			6,
			6,
			6,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5,
			5
		], d = [
			0,
			0,
			33554432,
			43046721,
			16777216,
			48828125,
			60466176,
			40353607,
			16777216,
			43046721,
			1e7,
			19487171,
			35831808,
			62748517,
			7529536,
			11390625,
			16777216,
			24137569,
			34012224,
			47045881,
			64e6,
			4084101,
			5153632,
			6436343,
			7962624,
			9765625,
			11881376,
			14348907,
			17210368,
			20511149,
			243e5,
			28629151,
			33554432,
			39135393,
			45435424,
			52521875,
			60466176
		];
		i.prototype.toString = function(e, t) {
			e ||= 10, t = t | 0 || 1;
			var r;
			if (e === 16 || e === "hex") {
				r = "";
				for (var i = 0, a = 0, o = 0; o < this.length; o++) {
					var s = this.words[o], c = ((s << i | a) & 16777215).toString(16);
					a = s >>> 24 - i & 16777215, i += 2, i >= 26 && (i -= 26, o--), r = a !== 0 || o !== this.length - 1 ? l[6 - c.length] + c + r : c + r;
				}
				for (a !== 0 && (r = a.toString(16) + r); r.length % t !== 0;) r = "0" + r;
				return this.negative !== 0 && (r = "-" + r), r;
			}
			if (e === (e | 0) && e >= 2 && e <= 36) {
				var f = u[e], p = d[e];
				r = "";
				var m = this.clone();
				for (m.negative = 0; !m.isZero();) {
					var h = m.modn(p).toString(e);
					m = m.idivn(p), r = m.isZero() ? h + r : l[f - h.length] + h + r;
				}
				for (this.isZero() && (r = "0" + r); r.length % t !== 0;) r = "0" + r;
				return this.negative !== 0 && (r = "-" + r), r;
			}
			n(!1, "Base should be between 2 and 36");
		}, i.prototype.toNumber = function() {
			var e = this.words[0];
			return this.length === 2 ? e += this.words[1] * 67108864 : this.length === 3 && this.words[2] === 1 ? e += 4503599627370496 + this.words[1] * 67108864 : this.length > 2 && n(!1, "Number can only safely store up to 53 bits"), this.negative === 0 ? e : -e;
		}, i.prototype.toJSON = function() {
			return this.toString(16);
		}, i.prototype.toBuffer = function(e, t) {
			return n(a !== void 0), this.toArrayLike(a, e, t);
		}, i.prototype.toArray = function(e, t) {
			return this.toArrayLike(Array, e, t);
		}, i.prototype.toArrayLike = function(e, t, r) {
			var i = this.byteLength(), a = r || Math.max(1, i);
			n(i <= a, "byte array longer than desired length"), n(a > 0, "Requested array length <= 0"), this.strip();
			var o = t === "le", s = new e(a), c, l, u = this.clone();
			if (o) {
				for (l = 0; !u.isZero(); l++) c = u.andln(255), u.iushrn(8), s[l] = c;
				for (; l < a; l++) s[l] = 0;
			} else {
				for (l = 0; l < a - i; l++) s[l] = 0;
				for (l = 0; !u.isZero(); l++) c = u.andln(255), u.iushrn(8), s[a - l - 1] = c;
			}
			return s;
		}, Math.clz32 ? i.prototype._countBits = function(e) {
			return 32 - Math.clz32(e);
		} : i.prototype._countBits = function(e) {
			var t = e, n = 0;
			return t >= 4096 && (n += 13, t >>>= 13), t >= 64 && (n += 7, t >>>= 7), t >= 8 && (n += 4, t >>>= 4), t >= 2 && (n += 2, t >>>= 2), n + t;
		}, i.prototype._zeroBits = function(e) {
			if (e === 0) return 26;
			var t = e, n = 0;
			return t & 8191 || (n += 13, t >>>= 13), t & 127 || (n += 7, t >>>= 7), t & 15 || (n += 4, t >>>= 4), t & 3 || (n += 2, t >>>= 2), t & 1 || n++, n;
		}, i.prototype.bitLength = function() {
			var e = this.words[this.length - 1], t = this._countBits(e);
			return (this.length - 1) * 26 + t;
		};
		function f(e) {
			for (var t = Array(e.bitLength()), n = 0; n < t.length; n++) {
				var r = n / 26 | 0, i = n % 26;
				t[n] = (e.words[r] & 1 << i) >>> i;
			}
			return t;
		}
		i.prototype.zeroBits = function() {
			if (this.isZero()) return 0;
			for (var e = 0, t = 0; t < this.length; t++) {
				var n = this._zeroBits(this.words[t]);
				if (e += n, n !== 26) break;
			}
			return e;
		}, i.prototype.byteLength = function() {
			return Math.ceil(this.bitLength() / 8);
		}, i.prototype.toTwos = function(e) {
			return this.negative === 0 ? this.clone() : this.abs().inotn(e).iaddn(1);
		}, i.prototype.fromTwos = function(e) {
			return this.testn(e - 1) ? this.notn(e).iaddn(1).ineg() : this.clone();
		}, i.prototype.isNeg = function() {
			return this.negative !== 0;
		}, i.prototype.neg = function() {
			return this.clone().ineg();
		}, i.prototype.ineg = function() {
			return this.isZero() || (this.negative ^= 1), this;
		}, i.prototype.iuor = function(e) {
			for (; this.length < e.length;) this.words[this.length++] = 0;
			for (var t = 0; t < e.length; t++) this.words[t] = this.words[t] | e.words[t];
			return this.strip();
		}, i.prototype.ior = function(e) {
			return n((this.negative | e.negative) === 0), this.iuor(e);
		}, i.prototype.or = function(e) {
			return this.length > e.length ? this.clone().ior(e) : e.clone().ior(this);
		}, i.prototype.uor = function(e) {
			return this.length > e.length ? this.clone().iuor(e) : e.clone().iuor(this);
		}, i.prototype.iuand = function(e) {
			for (var t = this.length > e.length ? e : this, n = 0; n < t.length; n++) this.words[n] = this.words[n] & e.words[n];
			return this.length = t.length, this.strip();
		}, i.prototype.iand = function(e) {
			return n((this.negative | e.negative) === 0), this.iuand(e);
		}, i.prototype.and = function(e) {
			return this.length > e.length ? this.clone().iand(e) : e.clone().iand(this);
		}, i.prototype.uand = function(e) {
			return this.length > e.length ? this.clone().iuand(e) : e.clone().iuand(this);
		}, i.prototype.iuxor = function(e) {
			var t, n;
			this.length > e.length ? (t = this, n = e) : (t = e, n = this);
			for (var r = 0; r < n.length; r++) this.words[r] = t.words[r] ^ n.words[r];
			if (this !== t) for (; r < t.length; r++) this.words[r] = t.words[r];
			return this.length = t.length, this.strip();
		}, i.prototype.ixor = function(e) {
			return n((this.negative | e.negative) === 0), this.iuxor(e);
		}, i.prototype.xor = function(e) {
			return this.length > e.length ? this.clone().ixor(e) : e.clone().ixor(this);
		}, i.prototype.uxor = function(e) {
			return this.length > e.length ? this.clone().iuxor(e) : e.clone().iuxor(this);
		}, i.prototype.inotn = function(e) {
			n(typeof e == "number" && e >= 0);
			var t = Math.ceil(e / 26) | 0, r = e % 26;
			this._expand(t), r > 0 && t--;
			for (var i = 0; i < t; i++) this.words[i] = ~this.words[i] & 67108863;
			return r > 0 && (this.words[i] = ~this.words[i] & 67108863 >> 26 - r), this.strip();
		}, i.prototype.notn = function(e) {
			return this.clone().inotn(e);
		}, i.prototype.setn = function(e, t) {
			n(typeof e == "number" && e >= 0);
			var r = e / 26 | 0, i = e % 26;
			return this._expand(r + 1), t ? this.words[r] = this.words[r] | 1 << i : this.words[r] = this.words[r] & ~(1 << i), this.strip();
		}, i.prototype.iadd = function(e) {
			var t;
			if (this.negative !== 0 && e.negative === 0) return this.negative = 0, t = this.isub(e), this.negative ^= 1, this._normSign();
			if (this.negative === 0 && e.negative !== 0) return e.negative = 0, t = this.isub(e), e.negative = 1, t._normSign();
			var n, r;
			this.length > e.length ? (n = this, r = e) : (n = e, r = this);
			for (var i = 0, a = 0; a < r.length; a++) t = (n.words[a] | 0) + (r.words[a] | 0) + i, this.words[a] = t & 67108863, i = t >>> 26;
			for (; i !== 0 && a < n.length; a++) t = (n.words[a] | 0) + i, this.words[a] = t & 67108863, i = t >>> 26;
			if (this.length = n.length, i !== 0) this.words[this.length] = i, this.length++;
			else if (n !== this) for (; a < n.length; a++) this.words[a] = n.words[a];
			return this;
		}, i.prototype.add = function(e) {
			var t;
			return e.negative !== 0 && this.negative === 0 ? (e.negative = 0, t = this.sub(e), e.negative ^= 1, t) : e.negative === 0 && this.negative !== 0 ? (this.negative = 0, t = e.sub(this), this.negative = 1, t) : this.length > e.length ? this.clone().iadd(e) : e.clone().iadd(this);
		}, i.prototype.isub = function(e) {
			if (e.negative !== 0) {
				e.negative = 0;
				var t = this.iadd(e);
				return e.negative = 1, t._normSign();
			} else if (this.negative !== 0) return this.negative = 0, this.iadd(e), this.negative = 1, this._normSign();
			var n = this.cmp(e);
			if (n === 0) return this.negative = 0, this.length = 1, this.words[0] = 0, this;
			var r, i;
			n > 0 ? (r = this, i = e) : (r = e, i = this);
			for (var a = 0, o = 0; o < i.length; o++) t = (r.words[o] | 0) - (i.words[o] | 0) + a, a = t >> 26, this.words[o] = t & 67108863;
			for (; a !== 0 && o < r.length; o++) t = (r.words[o] | 0) + a, a = t >> 26, this.words[o] = t & 67108863;
			if (a === 0 && o < r.length && r !== this) for (; o < r.length; o++) this.words[o] = r.words[o];
			return this.length = Math.max(this.length, o), r !== this && (this.negative = 1), this.strip();
		}, i.prototype.sub = function(e) {
			return this.clone().isub(e);
		};
		function p(e, t, n) {
			n.negative = t.negative ^ e.negative;
			var r = e.length + t.length | 0;
			n.length = r, r = r - 1 | 0;
			var i = e.words[0] | 0, a = t.words[0] | 0, o = i * a, s = o & 67108863, c = o / 67108864 | 0;
			n.words[0] = s;
			for (var l = 1; l < r; l++) {
				for (var u = c >>> 26, d = c & 67108863, f = Math.min(l, t.length - 1), p = Math.max(0, l - e.length + 1); p <= f; p++) {
					var m = l - p | 0;
					i = e.words[m] | 0, a = t.words[p] | 0, o = i * a + d, u += o / 67108864 | 0, d = o & 67108863;
				}
				n.words[l] = d | 0, c = u | 0;
			}
			return c === 0 ? n.length-- : n.words[l] = c | 0, n.strip();
		}
		var m = function(e, t, n) {
			var r = e.words, i = t.words, a = n.words, o = 0, s, c, l, u = r[0] | 0, d = u & 8191, f = u >>> 13, p = r[1] | 0, m = p & 8191, h = p >>> 13, g = r[2] | 0, _ = g & 8191, v = g >>> 13, y = r[3] | 0, b = y & 8191, x = y >>> 13, S = r[4] | 0, C = S & 8191, w = S >>> 13, T = r[5] | 0, E = T & 8191, D = T >>> 13, ee = r[6] | 0, O = ee & 8191, k = ee >>> 13, te = r[7] | 0, A = te & 8191, j = te >>> 13, ne = r[8] | 0, M = ne & 8191, N = ne >>> 13, re = r[9] | 0, ie = re & 8191, P = re >>> 13, ae = i[0] | 0, F = ae & 8191, oe = ae >>> 13, se = i[1] | 0, I = se & 8191, L = se >>> 13, ce = i[2] | 0, R = ce & 8191, le = ce >>> 13, ue = i[3] | 0, z = ue & 8191, B = ue >>> 13, de = i[4] | 0, fe = de & 8191, pe = de >>> 13, me = i[5] | 0, V = me & 8191, he = me >>> 13, ge = i[6] | 0, H = ge & 8191, U = ge >>> 13, _e = i[7] | 0, ve = _e & 8191, W = _e >>> 13, ye = i[8] | 0, be = ye & 8191, xe = ye >>> 13, Se = i[9] | 0, Ce = Se & 8191, we = Se >>> 13;
			n.negative = e.negative ^ t.negative, n.length = 19, s = Math.imul(d, F), c = Math.imul(d, oe), c = c + Math.imul(f, F) | 0, l = Math.imul(f, oe);
			var Te = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Te >>> 26) | 0, Te &= 67108863, s = Math.imul(m, F), c = Math.imul(m, oe), c = c + Math.imul(h, F) | 0, l = Math.imul(h, oe), s = s + Math.imul(d, I) | 0, c = c + Math.imul(d, L) | 0, c = c + Math.imul(f, I) | 0, l = l + Math.imul(f, L) | 0;
			var G = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (G >>> 26) | 0, G &= 67108863, s = Math.imul(_, F), c = Math.imul(_, oe), c = c + Math.imul(v, F) | 0, l = Math.imul(v, oe), s = s + Math.imul(m, I) | 0, c = c + Math.imul(m, L) | 0, c = c + Math.imul(h, I) | 0, l = l + Math.imul(h, L) | 0, s = s + Math.imul(d, R) | 0, c = c + Math.imul(d, le) | 0, c = c + Math.imul(f, R) | 0, l = l + Math.imul(f, le) | 0;
			var Ee = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Ee >>> 26) | 0, Ee &= 67108863, s = Math.imul(b, F), c = Math.imul(b, oe), c = c + Math.imul(x, F) | 0, l = Math.imul(x, oe), s = s + Math.imul(_, I) | 0, c = c + Math.imul(_, L) | 0, c = c + Math.imul(v, I) | 0, l = l + Math.imul(v, L) | 0, s = s + Math.imul(m, R) | 0, c = c + Math.imul(m, le) | 0, c = c + Math.imul(h, R) | 0, l = l + Math.imul(h, le) | 0, s = s + Math.imul(d, z) | 0, c = c + Math.imul(d, B) | 0, c = c + Math.imul(f, z) | 0, l = l + Math.imul(f, B) | 0;
			var De = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (De >>> 26) | 0, De &= 67108863, s = Math.imul(C, F), c = Math.imul(C, oe), c = c + Math.imul(w, F) | 0, l = Math.imul(w, oe), s = s + Math.imul(b, I) | 0, c = c + Math.imul(b, L) | 0, c = c + Math.imul(x, I) | 0, l = l + Math.imul(x, L) | 0, s = s + Math.imul(_, R) | 0, c = c + Math.imul(_, le) | 0, c = c + Math.imul(v, R) | 0, l = l + Math.imul(v, le) | 0, s = s + Math.imul(m, z) | 0, c = c + Math.imul(m, B) | 0, c = c + Math.imul(h, z) | 0, l = l + Math.imul(h, B) | 0, s = s + Math.imul(d, fe) | 0, c = c + Math.imul(d, pe) | 0, c = c + Math.imul(f, fe) | 0, l = l + Math.imul(f, pe) | 0;
			var Oe = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Oe >>> 26) | 0, Oe &= 67108863, s = Math.imul(E, F), c = Math.imul(E, oe), c = c + Math.imul(D, F) | 0, l = Math.imul(D, oe), s = s + Math.imul(C, I) | 0, c = c + Math.imul(C, L) | 0, c = c + Math.imul(w, I) | 0, l = l + Math.imul(w, L) | 0, s = s + Math.imul(b, R) | 0, c = c + Math.imul(b, le) | 0, c = c + Math.imul(x, R) | 0, l = l + Math.imul(x, le) | 0, s = s + Math.imul(_, z) | 0, c = c + Math.imul(_, B) | 0, c = c + Math.imul(v, z) | 0, l = l + Math.imul(v, B) | 0, s = s + Math.imul(m, fe) | 0, c = c + Math.imul(m, pe) | 0, c = c + Math.imul(h, fe) | 0, l = l + Math.imul(h, pe) | 0, s = s + Math.imul(d, V) | 0, c = c + Math.imul(d, he) | 0, c = c + Math.imul(f, V) | 0, l = l + Math.imul(f, he) | 0;
			var ke = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (ke >>> 26) | 0, ke &= 67108863, s = Math.imul(O, F), c = Math.imul(O, oe), c = c + Math.imul(k, F) | 0, l = Math.imul(k, oe), s = s + Math.imul(E, I) | 0, c = c + Math.imul(E, L) | 0, c = c + Math.imul(D, I) | 0, l = l + Math.imul(D, L) | 0, s = s + Math.imul(C, R) | 0, c = c + Math.imul(C, le) | 0, c = c + Math.imul(w, R) | 0, l = l + Math.imul(w, le) | 0, s = s + Math.imul(b, z) | 0, c = c + Math.imul(b, B) | 0, c = c + Math.imul(x, z) | 0, l = l + Math.imul(x, B) | 0, s = s + Math.imul(_, fe) | 0, c = c + Math.imul(_, pe) | 0, c = c + Math.imul(v, fe) | 0, l = l + Math.imul(v, pe) | 0, s = s + Math.imul(m, V) | 0, c = c + Math.imul(m, he) | 0, c = c + Math.imul(h, V) | 0, l = l + Math.imul(h, he) | 0, s = s + Math.imul(d, H) | 0, c = c + Math.imul(d, U) | 0, c = c + Math.imul(f, H) | 0, l = l + Math.imul(f, U) | 0;
			var Ae = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Ae >>> 26) | 0, Ae &= 67108863, s = Math.imul(A, F), c = Math.imul(A, oe), c = c + Math.imul(j, F) | 0, l = Math.imul(j, oe), s = s + Math.imul(O, I) | 0, c = c + Math.imul(O, L) | 0, c = c + Math.imul(k, I) | 0, l = l + Math.imul(k, L) | 0, s = s + Math.imul(E, R) | 0, c = c + Math.imul(E, le) | 0, c = c + Math.imul(D, R) | 0, l = l + Math.imul(D, le) | 0, s = s + Math.imul(C, z) | 0, c = c + Math.imul(C, B) | 0, c = c + Math.imul(w, z) | 0, l = l + Math.imul(w, B) | 0, s = s + Math.imul(b, fe) | 0, c = c + Math.imul(b, pe) | 0, c = c + Math.imul(x, fe) | 0, l = l + Math.imul(x, pe) | 0, s = s + Math.imul(_, V) | 0, c = c + Math.imul(_, he) | 0, c = c + Math.imul(v, V) | 0, l = l + Math.imul(v, he) | 0, s = s + Math.imul(m, H) | 0, c = c + Math.imul(m, U) | 0, c = c + Math.imul(h, H) | 0, l = l + Math.imul(h, U) | 0, s = s + Math.imul(d, ve) | 0, c = c + Math.imul(d, W) | 0, c = c + Math.imul(f, ve) | 0, l = l + Math.imul(f, W) | 0;
			var je = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (je >>> 26) | 0, je &= 67108863, s = Math.imul(M, F), c = Math.imul(M, oe), c = c + Math.imul(N, F) | 0, l = Math.imul(N, oe), s = s + Math.imul(A, I) | 0, c = c + Math.imul(A, L) | 0, c = c + Math.imul(j, I) | 0, l = l + Math.imul(j, L) | 0, s = s + Math.imul(O, R) | 0, c = c + Math.imul(O, le) | 0, c = c + Math.imul(k, R) | 0, l = l + Math.imul(k, le) | 0, s = s + Math.imul(E, z) | 0, c = c + Math.imul(E, B) | 0, c = c + Math.imul(D, z) | 0, l = l + Math.imul(D, B) | 0, s = s + Math.imul(C, fe) | 0, c = c + Math.imul(C, pe) | 0, c = c + Math.imul(w, fe) | 0, l = l + Math.imul(w, pe) | 0, s = s + Math.imul(b, V) | 0, c = c + Math.imul(b, he) | 0, c = c + Math.imul(x, V) | 0, l = l + Math.imul(x, he) | 0, s = s + Math.imul(_, H) | 0, c = c + Math.imul(_, U) | 0, c = c + Math.imul(v, H) | 0, l = l + Math.imul(v, U) | 0, s = s + Math.imul(m, ve) | 0, c = c + Math.imul(m, W) | 0, c = c + Math.imul(h, ve) | 0, l = l + Math.imul(h, W) | 0, s = s + Math.imul(d, be) | 0, c = c + Math.imul(d, xe) | 0, c = c + Math.imul(f, be) | 0, l = l + Math.imul(f, xe) | 0;
			var K = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (K >>> 26) | 0, K &= 67108863, s = Math.imul(ie, F), c = Math.imul(ie, oe), c = c + Math.imul(P, F) | 0, l = Math.imul(P, oe), s = s + Math.imul(M, I) | 0, c = c + Math.imul(M, L) | 0, c = c + Math.imul(N, I) | 0, l = l + Math.imul(N, L) | 0, s = s + Math.imul(A, R) | 0, c = c + Math.imul(A, le) | 0, c = c + Math.imul(j, R) | 0, l = l + Math.imul(j, le) | 0, s = s + Math.imul(O, z) | 0, c = c + Math.imul(O, B) | 0, c = c + Math.imul(k, z) | 0, l = l + Math.imul(k, B) | 0, s = s + Math.imul(E, fe) | 0, c = c + Math.imul(E, pe) | 0, c = c + Math.imul(D, fe) | 0, l = l + Math.imul(D, pe) | 0, s = s + Math.imul(C, V) | 0, c = c + Math.imul(C, he) | 0, c = c + Math.imul(w, V) | 0, l = l + Math.imul(w, he) | 0, s = s + Math.imul(b, H) | 0, c = c + Math.imul(b, U) | 0, c = c + Math.imul(x, H) | 0, l = l + Math.imul(x, U) | 0, s = s + Math.imul(_, ve) | 0, c = c + Math.imul(_, W) | 0, c = c + Math.imul(v, ve) | 0, l = l + Math.imul(v, W) | 0, s = s + Math.imul(m, be) | 0, c = c + Math.imul(m, xe) | 0, c = c + Math.imul(h, be) | 0, l = l + Math.imul(h, xe) | 0, s = s + Math.imul(d, Ce) | 0, c = c + Math.imul(d, we) | 0, c = c + Math.imul(f, Ce) | 0, l = l + Math.imul(f, we) | 0;
			var Me = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Me >>> 26) | 0, Me &= 67108863, s = Math.imul(ie, I), c = Math.imul(ie, L), c = c + Math.imul(P, I) | 0, l = Math.imul(P, L), s = s + Math.imul(M, R) | 0, c = c + Math.imul(M, le) | 0, c = c + Math.imul(N, R) | 0, l = l + Math.imul(N, le) | 0, s = s + Math.imul(A, z) | 0, c = c + Math.imul(A, B) | 0, c = c + Math.imul(j, z) | 0, l = l + Math.imul(j, B) | 0, s = s + Math.imul(O, fe) | 0, c = c + Math.imul(O, pe) | 0, c = c + Math.imul(k, fe) | 0, l = l + Math.imul(k, pe) | 0, s = s + Math.imul(E, V) | 0, c = c + Math.imul(E, he) | 0, c = c + Math.imul(D, V) | 0, l = l + Math.imul(D, he) | 0, s = s + Math.imul(C, H) | 0, c = c + Math.imul(C, U) | 0, c = c + Math.imul(w, H) | 0, l = l + Math.imul(w, U) | 0, s = s + Math.imul(b, ve) | 0, c = c + Math.imul(b, W) | 0, c = c + Math.imul(x, ve) | 0, l = l + Math.imul(x, W) | 0, s = s + Math.imul(_, be) | 0, c = c + Math.imul(_, xe) | 0, c = c + Math.imul(v, be) | 0, l = l + Math.imul(v, xe) | 0, s = s + Math.imul(m, Ce) | 0, c = c + Math.imul(m, we) | 0, c = c + Math.imul(h, Ce) | 0, l = l + Math.imul(h, we) | 0;
			var Ne = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Ne >>> 26) | 0, Ne &= 67108863, s = Math.imul(ie, R), c = Math.imul(ie, le), c = c + Math.imul(P, R) | 0, l = Math.imul(P, le), s = s + Math.imul(M, z) | 0, c = c + Math.imul(M, B) | 0, c = c + Math.imul(N, z) | 0, l = l + Math.imul(N, B) | 0, s = s + Math.imul(A, fe) | 0, c = c + Math.imul(A, pe) | 0, c = c + Math.imul(j, fe) | 0, l = l + Math.imul(j, pe) | 0, s = s + Math.imul(O, V) | 0, c = c + Math.imul(O, he) | 0, c = c + Math.imul(k, V) | 0, l = l + Math.imul(k, he) | 0, s = s + Math.imul(E, H) | 0, c = c + Math.imul(E, U) | 0, c = c + Math.imul(D, H) | 0, l = l + Math.imul(D, U) | 0, s = s + Math.imul(C, ve) | 0, c = c + Math.imul(C, W) | 0, c = c + Math.imul(w, ve) | 0, l = l + Math.imul(w, W) | 0, s = s + Math.imul(b, be) | 0, c = c + Math.imul(b, xe) | 0, c = c + Math.imul(x, be) | 0, l = l + Math.imul(x, xe) | 0, s = s + Math.imul(_, Ce) | 0, c = c + Math.imul(_, we) | 0, c = c + Math.imul(v, Ce) | 0, l = l + Math.imul(v, we) | 0;
			var Pe = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Pe >>> 26) | 0, Pe &= 67108863, s = Math.imul(ie, z), c = Math.imul(ie, B), c = c + Math.imul(P, z) | 0, l = Math.imul(P, B), s = s + Math.imul(M, fe) | 0, c = c + Math.imul(M, pe) | 0, c = c + Math.imul(N, fe) | 0, l = l + Math.imul(N, pe) | 0, s = s + Math.imul(A, V) | 0, c = c + Math.imul(A, he) | 0, c = c + Math.imul(j, V) | 0, l = l + Math.imul(j, he) | 0, s = s + Math.imul(O, H) | 0, c = c + Math.imul(O, U) | 0, c = c + Math.imul(k, H) | 0, l = l + Math.imul(k, U) | 0, s = s + Math.imul(E, ve) | 0, c = c + Math.imul(E, W) | 0, c = c + Math.imul(D, ve) | 0, l = l + Math.imul(D, W) | 0, s = s + Math.imul(C, be) | 0, c = c + Math.imul(C, xe) | 0, c = c + Math.imul(w, be) | 0, l = l + Math.imul(w, xe) | 0, s = s + Math.imul(b, Ce) | 0, c = c + Math.imul(b, we) | 0, c = c + Math.imul(x, Ce) | 0, l = l + Math.imul(x, we) | 0;
			var Fe = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Fe >>> 26) | 0, Fe &= 67108863, s = Math.imul(ie, fe), c = Math.imul(ie, pe), c = c + Math.imul(P, fe) | 0, l = Math.imul(P, pe), s = s + Math.imul(M, V) | 0, c = c + Math.imul(M, he) | 0, c = c + Math.imul(N, V) | 0, l = l + Math.imul(N, he) | 0, s = s + Math.imul(A, H) | 0, c = c + Math.imul(A, U) | 0, c = c + Math.imul(j, H) | 0, l = l + Math.imul(j, U) | 0, s = s + Math.imul(O, ve) | 0, c = c + Math.imul(O, W) | 0, c = c + Math.imul(k, ve) | 0, l = l + Math.imul(k, W) | 0, s = s + Math.imul(E, be) | 0, c = c + Math.imul(E, xe) | 0, c = c + Math.imul(D, be) | 0, l = l + Math.imul(D, xe) | 0, s = s + Math.imul(C, Ce) | 0, c = c + Math.imul(C, we) | 0, c = c + Math.imul(w, Ce) | 0, l = l + Math.imul(w, we) | 0;
			var Ie = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Ie >>> 26) | 0, Ie &= 67108863, s = Math.imul(ie, V), c = Math.imul(ie, he), c = c + Math.imul(P, V) | 0, l = Math.imul(P, he), s = s + Math.imul(M, H) | 0, c = c + Math.imul(M, U) | 0, c = c + Math.imul(N, H) | 0, l = l + Math.imul(N, U) | 0, s = s + Math.imul(A, ve) | 0, c = c + Math.imul(A, W) | 0, c = c + Math.imul(j, ve) | 0, l = l + Math.imul(j, W) | 0, s = s + Math.imul(O, be) | 0, c = c + Math.imul(O, xe) | 0, c = c + Math.imul(k, be) | 0, l = l + Math.imul(k, xe) | 0, s = s + Math.imul(E, Ce) | 0, c = c + Math.imul(E, we) | 0, c = c + Math.imul(D, Ce) | 0, l = l + Math.imul(D, we) | 0;
			var q = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (q >>> 26) | 0, q &= 67108863, s = Math.imul(ie, H), c = Math.imul(ie, U), c = c + Math.imul(P, H) | 0, l = Math.imul(P, U), s = s + Math.imul(M, ve) | 0, c = c + Math.imul(M, W) | 0, c = c + Math.imul(N, ve) | 0, l = l + Math.imul(N, W) | 0, s = s + Math.imul(A, be) | 0, c = c + Math.imul(A, xe) | 0, c = c + Math.imul(j, be) | 0, l = l + Math.imul(j, xe) | 0, s = s + Math.imul(O, Ce) | 0, c = c + Math.imul(O, we) | 0, c = c + Math.imul(k, Ce) | 0, l = l + Math.imul(k, we) | 0;
			var Le = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Le >>> 26) | 0, Le &= 67108863, s = Math.imul(ie, ve), c = Math.imul(ie, W), c = c + Math.imul(P, ve) | 0, l = Math.imul(P, W), s = s + Math.imul(M, be) | 0, c = c + Math.imul(M, xe) | 0, c = c + Math.imul(N, be) | 0, l = l + Math.imul(N, xe) | 0, s = s + Math.imul(A, Ce) | 0, c = c + Math.imul(A, we) | 0, c = c + Math.imul(j, Ce) | 0, l = l + Math.imul(j, we) | 0;
			var Re = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (Re >>> 26) | 0, Re &= 67108863, s = Math.imul(ie, be), c = Math.imul(ie, xe), c = c + Math.imul(P, be) | 0, l = Math.imul(P, xe), s = s + Math.imul(M, Ce) | 0, c = c + Math.imul(M, we) | 0, c = c + Math.imul(N, Ce) | 0, l = l + Math.imul(N, we) | 0;
			var ze = (o + s | 0) + ((c & 8191) << 13) | 0;
			o = (l + (c >>> 13) | 0) + (ze >>> 26) | 0, ze &= 67108863, s = Math.imul(ie, Ce), c = Math.imul(ie, we), c = c + Math.imul(P, Ce) | 0, l = Math.imul(P, we);
			var Be = (o + s | 0) + ((c & 8191) << 13) | 0;
			return o = (l + (c >>> 13) | 0) + (Be >>> 26) | 0, Be &= 67108863, a[0] = Te, a[1] = G, a[2] = Ee, a[3] = De, a[4] = Oe, a[5] = ke, a[6] = Ae, a[7] = je, a[8] = K, a[9] = Me, a[10] = Ne, a[11] = Pe, a[12] = Fe, a[13] = Ie, a[14] = q, a[15] = Le, a[16] = Re, a[17] = ze, a[18] = Be, o !== 0 && (a[19] = o, n.length++), n;
		};
		Math.imul || (m = p);
		function h(e, t, n) {
			n.negative = t.negative ^ e.negative, n.length = e.length + t.length;
			for (var r = 0, i = 0, a = 0; a < n.length - 1; a++) {
				var o = i;
				i = 0;
				for (var s = r & 67108863, c = Math.min(a, t.length - 1), l = Math.max(0, a - e.length + 1); l <= c; l++) {
					var u = a - l, d = (e.words[u] | 0) * (t.words[l] | 0), f = d & 67108863;
					o = o + (d / 67108864 | 0) | 0, f = f + s | 0, s = f & 67108863, o = o + (f >>> 26) | 0, i += o >>> 26, o &= 67108863;
				}
				n.words[a] = s, r = o, o = i;
			}
			return r === 0 ? n.length-- : n.words[a] = r, n.strip();
		}
		function g(e, t, n) {
			return new _().mulp(e, t, n);
		}
		i.prototype.mulTo = function(e, t) {
			var n, r = this.length + e.length;
			return n = this.length === 10 && e.length === 10 ? m(this, e, t) : r < 63 ? p(this, e, t) : r < 1024 ? h(this, e, t) : g(this, e, t), n;
		};
		function _(e, t) {
			this.x = e, this.y = t;
		}
		_.prototype.makeRBT = function(e) {
			for (var t = Array(e), n = i.prototype._countBits(e) - 1, r = 0; r < e; r++) t[r] = this.revBin(r, n, e);
			return t;
		}, _.prototype.revBin = function(e, t, n) {
			if (e === 0 || e === n - 1) return e;
			for (var r = 0, i = 0; i < t; i++) r |= (e & 1) << t - i - 1, e >>= 1;
			return r;
		}, _.prototype.permute = function(e, t, n, r, i, a) {
			for (var o = 0; o < a; o++) r[o] = t[e[o]], i[o] = n[e[o]];
		}, _.prototype.transform = function(e, t, n, r, i, a) {
			this.permute(a, e, t, n, r, i);
			for (var o = 1; o < i; o <<= 1) for (var s = o << 1, c = Math.cos(2 * Math.PI / s), l = Math.sin(2 * Math.PI / s), u = 0; u < i; u += s) for (var d = c, f = l, p = 0; p < o; p++) {
				var m = n[u + p], h = r[u + p], g = n[u + p + o], _ = r[u + p + o], v = d * g - f * _;
				_ = d * _ + f * g, g = v, n[u + p] = m + g, r[u + p] = h + _, n[u + p + o] = m - g, r[u + p + o] = h - _, p !== s && (v = c * d - l * f, f = c * f + l * d, d = v);
			}
		}, _.prototype.guessLen13b = function(e, t) {
			var n = Math.max(t, e) | 1, r = n & 1, i = 0;
			for (n = n / 2 | 0; n; n >>>= 1) i++;
			return 1 << i + 1 + r;
		}, _.prototype.conjugate = function(e, t, n) {
			if (!(n <= 1)) for (var r = 0; r < n / 2; r++) {
				var i = e[r];
				e[r] = e[n - r - 1], e[n - r - 1] = i, i = t[r], t[r] = -t[n - r - 1], t[n - r - 1] = -i;
			}
		}, _.prototype.normalize13b = function(e, t) {
			for (var n = 0, r = 0; r < t / 2; r++) {
				var i = Math.round(e[2 * r + 1] / t) * 8192 + Math.round(e[2 * r] / t) + n;
				e[r] = i & 67108863, n = i < 67108864 ? 0 : i / 67108864 | 0;
			}
			return e;
		}, _.prototype.convert13b = function(e, t, r, i) {
			for (var a = 0, o = 0; o < t; o++) a += e[o] | 0, r[2 * o] = a & 8191, a >>>= 13, r[2 * o + 1] = a & 8191, a >>>= 13;
			for (o = 2 * t; o < i; ++o) r[o] = 0;
			n(a === 0), n((a & -8192) == 0);
		}, _.prototype.stub = function(e) {
			for (var t = Array(e), n = 0; n < e; n++) t[n] = 0;
			return t;
		}, _.prototype.mulp = function(e, t, n) {
			var r = 2 * this.guessLen13b(e.length, t.length), i = this.makeRBT(r), a = this.stub(r), o = Array(r), s = Array(r), c = Array(r), l = Array(r), u = Array(r), d = Array(r), f = n.words;
			f.length = r, this.convert13b(e.words, e.length, o, r), this.convert13b(t.words, t.length, l, r), this.transform(o, a, s, c, r, i), this.transform(l, a, u, d, r, i);
			for (var p = 0; p < r; p++) {
				var m = s[p] * u[p] - c[p] * d[p];
				c[p] = s[p] * d[p] + c[p] * u[p], s[p] = m;
			}
			return this.conjugate(s, c, r), this.transform(s, c, f, a, r, i), this.conjugate(f, a, r), this.normalize13b(f, r), n.negative = e.negative ^ t.negative, n.length = e.length + t.length, n.strip();
		}, i.prototype.mul = function(e) {
			var t = new i(null);
			return t.words = Array(this.length + e.length), this.mulTo(e, t);
		}, i.prototype.mulf = function(e) {
			var t = new i(null);
			return t.words = Array(this.length + e.length), g(this, e, t);
		}, i.prototype.imul = function(e) {
			return this.clone().mulTo(e, this);
		}, i.prototype.imuln = function(e) {
			n(typeof e == "number"), n(e < 67108864);
			for (var t = 0, r = 0; r < this.length; r++) {
				var i = (this.words[r] | 0) * e, a = (i & 67108863) + (t & 67108863);
				t >>= 26, t += i / 67108864 | 0, t += a >>> 26, this.words[r] = a & 67108863;
			}
			return t !== 0 && (this.words[r] = t, this.length++), this.length = e === 0 ? 1 : this.length, this;
		}, i.prototype.muln = function(e) {
			return this.clone().imuln(e);
		}, i.prototype.sqr = function() {
			return this.mul(this);
		}, i.prototype.isqr = function() {
			return this.imul(this.clone());
		}, i.prototype.pow = function(e) {
			var t = f(e);
			if (t.length === 0) return new i(1);
			for (var n = this, r = 0; r < t.length && t[r] === 0; r++, n = n.sqr());
			if (++r < t.length) for (var a = n.sqr(); r < t.length; r++, a = a.sqr()) t[r] !== 0 && (n = n.mul(a));
			return n;
		}, i.prototype.iushln = function(e) {
			n(typeof e == "number" && e >= 0);
			var t = e % 26, r = (e - t) / 26, i = 67108863 >>> 26 - t << 26 - t, a;
			if (t !== 0) {
				var o = 0;
				for (a = 0; a < this.length; a++) {
					var s = this.words[a] & i, c = (this.words[a] | 0) - s << t;
					this.words[a] = c | o, o = s >>> 26 - t;
				}
				o && (this.words[a] = o, this.length++);
			}
			if (r !== 0) {
				for (a = this.length - 1; a >= 0; a--) this.words[a + r] = this.words[a];
				for (a = 0; a < r; a++) this.words[a] = 0;
				this.length += r;
			}
			return this.strip();
		}, i.prototype.ishln = function(e) {
			return n(this.negative === 0), this.iushln(e);
		}, i.prototype.iushrn = function(e, t, r) {
			n(typeof e == "number" && e >= 0);
			var i = t ? (t - t % 26) / 26 : 0, a = e % 26, o = Math.min((e - a) / 26, this.length), s = 67108863 ^ 67108863 >>> a << a, c = r;
			if (i -= o, i = Math.max(0, i), c) {
				for (var l = 0; l < o; l++) c.words[l] = this.words[l];
				c.length = o;
			}
			if (o !== 0) if (this.length > o) for (this.length -= o, l = 0; l < this.length; l++) this.words[l] = this.words[l + o];
			else this.words[0] = 0, this.length = 1;
			var u = 0;
			for (l = this.length - 1; l >= 0 && (u !== 0 || l >= i); l--) {
				var d = this.words[l] | 0;
				this.words[l] = u << 26 - a | d >>> a, u = d & s;
			}
			return c && u !== 0 && (c.words[c.length++] = u), this.length === 0 && (this.words[0] = 0, this.length = 1), this.strip();
		}, i.prototype.ishrn = function(e, t, r) {
			return n(this.negative === 0), this.iushrn(e, t, r);
		}, i.prototype.shln = function(e) {
			return this.clone().ishln(e);
		}, i.prototype.ushln = function(e) {
			return this.clone().iushln(e);
		}, i.prototype.shrn = function(e) {
			return this.clone().ishrn(e);
		}, i.prototype.ushrn = function(e) {
			return this.clone().iushrn(e);
		}, i.prototype.testn = function(e) {
			n(typeof e == "number" && e >= 0);
			var t = e % 26, r = (e - t) / 26, i = 1 << t;
			return this.length <= r ? !1 : !!(this.words[r] & i);
		}, i.prototype.imaskn = function(e) {
			n(typeof e == "number" && e >= 0);
			var t = e % 26, r = (e - t) / 26;
			if (n(this.negative === 0, "imaskn works only with positive numbers"), this.length <= r) return this;
			if (t !== 0 && r++, this.length = Math.min(r, this.length), t !== 0) {
				var i = 67108863 ^ 67108863 >>> t << t;
				this.words[this.length - 1] &= i;
			}
			return this.length === 0 && (this.words[0] = 0, this.length = 1), this.strip();
		}, i.prototype.maskn = function(e) {
			return this.clone().imaskn(e);
		}, i.prototype.iaddn = function(e) {
			return n(typeof e == "number"), n(e < 67108864), e < 0 ? this.isubn(-e) : this.negative === 0 ? this._iaddn(e) : this.length === 1 && (this.words[0] | 0) < e ? (this.words[0] = e - (this.words[0] | 0), this.negative = 0, this) : (this.negative = 0, this.isubn(e), this.negative = 1, this);
		}, i.prototype._iaddn = function(e) {
			this.words[0] += e;
			for (var t = 0; t < this.length && this.words[t] >= 67108864; t++) this.words[t] -= 67108864, t === this.length - 1 ? this.words[t + 1] = 1 : this.words[t + 1]++;
			return this.length = Math.max(this.length, t + 1), this;
		}, i.prototype.isubn = function(e) {
			if (n(typeof e == "number"), n(e < 67108864), e < 0) return this.iaddn(-e);
			if (this.negative !== 0) return this.negative = 0, this.iaddn(e), this.negative = 1, this;
			if (this.words[0] -= e, this.length === 1 && this.words[0] < 0) this.words[0] = -this.words[0], this.negative = 1;
			else for (var t = 0; t < this.length && this.words[t] < 0; t++) this.words[t] += 67108864, --this.words[t + 1];
			return this.strip();
		}, i.prototype.addn = function(e) {
			return this.clone().iaddn(e);
		}, i.prototype.subn = function(e) {
			return this.clone().isubn(e);
		}, i.prototype.iabs = function() {
			return this.negative = 0, this;
		}, i.prototype.abs = function() {
			return this.clone().iabs();
		}, i.prototype._ishlnsubmul = function(e, t, r) {
			var i = e.length + r, a;
			this._expand(i);
			var o, s = 0;
			for (a = 0; a < e.length; a++) {
				o = (this.words[a + r] | 0) + s;
				var c = (e.words[a] | 0) * t;
				o -= c & 67108863, s = (o >> 26) - (c / 67108864 | 0), this.words[a + r] = o & 67108863;
			}
			for (; a < this.length - r; a++) o = (this.words[a + r] | 0) + s, s = o >> 26, this.words[a + r] = o & 67108863;
			if (s === 0) return this.strip();
			for (n(s === -1), s = 0, a = 0; a < this.length; a++) o = -(this.words[a] | 0) + s, s = o >> 26, this.words[a] = o & 67108863;
			return this.negative = 1, this.strip();
		}, i.prototype._wordDiv = function(e, t) {
			var n = this.length - e.length, r = this.clone(), a = e, o = a.words[a.length - 1] | 0;
			n = 26 - this._countBits(o), n !== 0 && (a = a.ushln(n), r.iushln(n), o = a.words[a.length - 1] | 0);
			var s = r.length - a.length, c;
			if (t !== "mod") {
				c = new i(null), c.length = s + 1, c.words = Array(c.length);
				for (var l = 0; l < c.length; l++) c.words[l] = 0;
			}
			var u = r.clone()._ishlnsubmul(a, 1, s);
			u.negative === 0 && (r = u, c && (c.words[s] = 1));
			for (var d = s - 1; d >= 0; d--) {
				var f = (r.words[a.length + d] | 0) * 67108864 + (r.words[a.length + d - 1] | 0);
				for (f = Math.min(f / o | 0, 67108863), r._ishlnsubmul(a, f, d); r.negative !== 0;) f--, r.negative = 0, r._ishlnsubmul(a, 1, d), r.isZero() || (r.negative ^= 1);
				c && (c.words[d] = f);
			}
			return c && c.strip(), r.strip(), t !== "div" && n !== 0 && r.iushrn(n), {
				div: c || null,
				mod: r
			};
		}, i.prototype.divmod = function(e, t, r) {
			if (n(!e.isZero()), this.isZero()) return {
				div: new i(0),
				mod: new i(0)
			};
			var a, o, s;
			return this.negative !== 0 && e.negative === 0 ? (s = this.neg().divmod(e, t), t !== "mod" && (a = s.div.neg()), t !== "div" && (o = s.mod.neg(), r && o.negative !== 0 && o.iadd(e)), {
				div: a,
				mod: o
			}) : this.negative === 0 && e.negative !== 0 ? (s = this.divmod(e.neg(), t), t !== "mod" && (a = s.div.neg()), {
				div: a,
				mod: s.mod
			}) : (this.negative & e.negative) === 0 ? e.length > this.length || this.cmp(e) < 0 ? {
				div: new i(0),
				mod: this
			} : e.length === 1 ? t === "div" ? {
				div: this.divn(e.words[0]),
				mod: null
			} : t === "mod" ? {
				div: null,
				mod: new i(this.modn(e.words[0]))
			} : {
				div: this.divn(e.words[0]),
				mod: new i(this.modn(e.words[0]))
			} : this._wordDiv(e, t) : (s = this.neg().divmod(e.neg(), t), t !== "div" && (o = s.mod.neg(), r && o.negative !== 0 && o.isub(e)), {
				div: s.div,
				mod: o
			});
		}, i.prototype.div = function(e) {
			return this.divmod(e, "div", !1).div;
		}, i.prototype.mod = function(e) {
			return this.divmod(e, "mod", !1).mod;
		}, i.prototype.umod = function(e) {
			return this.divmod(e, "mod", !0).mod;
		}, i.prototype.divRound = function(e) {
			var t = this.divmod(e);
			if (t.mod.isZero()) return t.div;
			var n = t.div.negative === 0 ? t.mod : t.mod.isub(e), r = e.ushrn(1), i = e.andln(1), a = n.cmp(r);
			return a < 0 || i === 1 && a === 0 ? t.div : t.div.negative === 0 ? t.div.iaddn(1) : t.div.isubn(1);
		}, i.prototype.modn = function(e) {
			n(e <= 67108863);
			for (var t = (1 << 26) % e, r = 0, i = this.length - 1; i >= 0; i--) r = (t * r + (this.words[i] | 0)) % e;
			return r;
		}, i.prototype.idivn = function(e) {
			n(e <= 67108863);
			for (var t = 0, r = this.length - 1; r >= 0; r--) {
				var i = (this.words[r] | 0) + t * 67108864;
				this.words[r] = i / e | 0, t = i % e;
			}
			return this.strip();
		}, i.prototype.divn = function(e) {
			return this.clone().idivn(e);
		}, i.prototype.egcd = function(e) {
			n(e.negative === 0), n(!e.isZero());
			var t = this, r = e.clone();
			t = t.negative === 0 ? t.clone() : t.umod(e);
			for (var a = new i(1), o = new i(0), s = new i(0), c = new i(1), l = 0; t.isEven() && r.isEven();) t.iushrn(1), r.iushrn(1), ++l;
			for (var u = r.clone(), d = t.clone(); !t.isZero();) {
				for (var f = 0, p = 1; (t.words[0] & p) === 0 && f < 26; ++f, p <<= 1);
				if (f > 0) for (t.iushrn(f); f-- > 0;) (a.isOdd() || o.isOdd()) && (a.iadd(u), o.isub(d)), a.iushrn(1), o.iushrn(1);
				for (var m = 0, h = 1; (r.words[0] & h) === 0 && m < 26; ++m, h <<= 1);
				if (m > 0) for (r.iushrn(m); m-- > 0;) (s.isOdd() || c.isOdd()) && (s.iadd(u), c.isub(d)), s.iushrn(1), c.iushrn(1);
				t.cmp(r) >= 0 ? (t.isub(r), a.isub(s), o.isub(c)) : (r.isub(t), s.isub(a), c.isub(o));
			}
			return {
				a: s,
				b: c,
				gcd: r.iushln(l)
			};
		}, i.prototype._invmp = function(e) {
			n(e.negative === 0), n(!e.isZero());
			var t = this, r = e.clone();
			t = t.negative === 0 ? t.clone() : t.umod(e);
			for (var a = new i(1), o = new i(0), s = r.clone(); t.cmpn(1) > 0 && r.cmpn(1) > 0;) {
				for (var c = 0, l = 1; (t.words[0] & l) === 0 && c < 26; ++c, l <<= 1);
				if (c > 0) for (t.iushrn(c); c-- > 0;) a.isOdd() && a.iadd(s), a.iushrn(1);
				for (var u = 0, d = 1; (r.words[0] & d) === 0 && u < 26; ++u, d <<= 1);
				if (u > 0) for (r.iushrn(u); u-- > 0;) o.isOdd() && o.iadd(s), o.iushrn(1);
				t.cmp(r) >= 0 ? (t.isub(r), a.isub(o)) : (r.isub(t), o.isub(a));
			}
			var f = t.cmpn(1) === 0 ? a : o;
			return f.cmpn(0) < 0 && f.iadd(e), f;
		}, i.prototype.gcd = function(e) {
			if (this.isZero()) return e.abs();
			if (e.isZero()) return this.abs();
			var t = this.clone(), n = e.clone();
			t.negative = 0, n.negative = 0;
			for (var r = 0; t.isEven() && n.isEven(); r++) t.iushrn(1), n.iushrn(1);
			do {
				for (; t.isEven();) t.iushrn(1);
				for (; n.isEven();) n.iushrn(1);
				var i = t.cmp(n);
				if (i < 0) {
					var a = t;
					t = n, n = a;
				} else if (i === 0 || n.cmpn(1) === 0) break;
				t.isub(n);
			} while (!0);
			return n.iushln(r);
		}, i.prototype.invm = function(e) {
			return this.egcd(e).a.umod(e);
		}, i.prototype.isEven = function() {
			return (this.words[0] & 1) == 0;
		}, i.prototype.isOdd = function() {
			return (this.words[0] & 1) == 1;
		}, i.prototype.andln = function(e) {
			return this.words[0] & e;
		}, i.prototype.bincn = function(e) {
			n(typeof e == "number");
			var t = e % 26, r = (e - t) / 26, i = 1 << t;
			if (this.length <= r) return this._expand(r + 1), this.words[r] |= i, this;
			for (var a = i, o = r; a !== 0 && o < this.length; o++) {
				var s = this.words[o] | 0;
				s += a, a = s >>> 26, s &= 67108863, this.words[o] = s;
			}
			return a !== 0 && (this.words[o] = a, this.length++), this;
		}, i.prototype.isZero = function() {
			return this.length === 1 && this.words[0] === 0;
		}, i.prototype.cmpn = function(e) {
			var t = e < 0;
			if (this.negative !== 0 && !t) return -1;
			if (this.negative === 0 && t) return 1;
			this.strip();
			var r;
			if (this.length > 1) r = 1;
			else {
				t && (e = -e), n(e <= 67108863, "Number is too big");
				var i = this.words[0] | 0;
				r = i === e ? 0 : i < e ? -1 : 1;
			}
			return this.negative === 0 ? r : -r | 0;
		}, i.prototype.cmp = function(e) {
			if (this.negative !== 0 && e.negative === 0) return -1;
			if (this.negative === 0 && e.negative !== 0) return 1;
			var t = this.ucmp(e);
			return this.negative === 0 ? t : -t | 0;
		}, i.prototype.ucmp = function(e) {
			if (this.length > e.length) return 1;
			if (this.length < e.length) return -1;
			for (var t = 0, n = this.length - 1; n >= 0; n--) {
				var r = this.words[n] | 0, i = e.words[n] | 0;
				if (r !== i) {
					r < i ? t = -1 : r > i && (t = 1);
					break;
				}
			}
			return t;
		}, i.prototype.gtn = function(e) {
			return this.cmpn(e) === 1;
		}, i.prototype.gt = function(e) {
			return this.cmp(e) === 1;
		}, i.prototype.gten = function(e) {
			return this.cmpn(e) >= 0;
		}, i.prototype.gte = function(e) {
			return this.cmp(e) >= 0;
		}, i.prototype.ltn = function(e) {
			return this.cmpn(e) === -1;
		}, i.prototype.lt = function(e) {
			return this.cmp(e) === -1;
		}, i.prototype.lten = function(e) {
			return this.cmpn(e) <= 0;
		}, i.prototype.lte = function(e) {
			return this.cmp(e) <= 0;
		}, i.prototype.eqn = function(e) {
			return this.cmpn(e) === 0;
		}, i.prototype.eq = function(e) {
			return this.cmp(e) === 0;
		}, i.red = function(e) {
			return new w(e);
		}, i.prototype.toRed = function(e) {
			return n(!this.red, "Already a number in reduction context"), n(this.negative === 0, "red works only with positives"), e.convertTo(this)._forceRed(e);
		}, i.prototype.fromRed = function() {
			return n(this.red, "fromRed works only with numbers in reduction context"), this.red.convertFrom(this);
		}, i.prototype._forceRed = function(e) {
			return this.red = e, this;
		}, i.prototype.forceRed = function(e) {
			return n(!this.red, "Already a number in reduction context"), this._forceRed(e);
		}, i.prototype.redAdd = function(e) {
			return n(this.red, "redAdd works only with red numbers"), this.red.add(this, e);
		}, i.prototype.redIAdd = function(e) {
			return n(this.red, "redIAdd works only with red numbers"), this.red.iadd(this, e);
		}, i.prototype.redSub = function(e) {
			return n(this.red, "redSub works only with red numbers"), this.red.sub(this, e);
		}, i.prototype.redISub = function(e) {
			return n(this.red, "redISub works only with red numbers"), this.red.isub(this, e);
		}, i.prototype.redShl = function(e) {
			return n(this.red, "redShl works only with red numbers"), this.red.shl(this, e);
		}, i.prototype.redMul = function(e) {
			return n(this.red, "redMul works only with red numbers"), this.red._verify2(this, e), this.red.mul(this, e);
		}, i.prototype.redIMul = function(e) {
			return n(this.red, "redMul works only with red numbers"), this.red._verify2(this, e), this.red.imul(this, e);
		}, i.prototype.redSqr = function() {
			return n(this.red, "redSqr works only with red numbers"), this.red._verify1(this), this.red.sqr(this);
		}, i.prototype.redISqr = function() {
			return n(this.red, "redISqr works only with red numbers"), this.red._verify1(this), this.red.isqr(this);
		}, i.prototype.redSqrt = function() {
			return n(this.red, "redSqrt works only with red numbers"), this.red._verify1(this), this.red.sqrt(this);
		}, i.prototype.redInvm = function() {
			return n(this.red, "redInvm works only with red numbers"), this.red._verify1(this), this.red.invm(this);
		}, i.prototype.redNeg = function() {
			return n(this.red, "redNeg works only with red numbers"), this.red._verify1(this), this.red.neg(this);
		}, i.prototype.redPow = function(e) {
			return n(this.red && !e.red, "redPow(normalNum)"), this.red._verify1(this), this.red.pow(this, e);
		};
		var v = {
			k256: null,
			p224: null,
			p192: null,
			p25519: null
		};
		function y(e, t) {
			this.name = e, this.p = new i(t, 16), this.n = this.p.bitLength(), this.k = new i(1).iushln(this.n).isub(this.p), this.tmp = this._tmp();
		}
		y.prototype._tmp = function() {
			var e = new i(null);
			return e.words = Array(Math.ceil(this.n / 13)), e;
		}, y.prototype.ireduce = function(e) {
			var t = e, n;
			do
				this.split(t, this.tmp), t = this.imulK(t), t = t.iadd(this.tmp), n = t.bitLength();
			while (n > this.n);
			var r = n < this.n ? -1 : t.ucmp(this.p);
			return r === 0 ? (t.words[0] = 0, t.length = 1) : r > 0 ? t.isub(this.p) : t.strip === void 0 ? t._strip() : t.strip(), t;
		}, y.prototype.split = function(e, t) {
			e.iushrn(this.n, 0, t);
		}, y.prototype.imulK = function(e) {
			return e.imul(this.k);
		};
		function b() {
			y.call(this, "k256", "ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffe fffffc2f");
		}
		r(b, y), b.prototype.split = function(e, t) {
			for (var n = 4194303, r = Math.min(e.length, 9), i = 0; i < r; i++) t.words[i] = e.words[i];
			if (t.length = r, e.length <= 9) {
				e.words[0] = 0, e.length = 1;
				return;
			}
			var a = e.words[9];
			for (t.words[t.length++] = a & n, i = 10; i < e.length; i++) {
				var o = e.words[i] | 0;
				e.words[i - 10] = (o & n) << 4 | a >>> 22, a = o;
			}
			a >>>= 22, e.words[i - 10] = a, a === 0 && e.length > 10 ? e.length -= 10 : e.length -= 9;
		}, b.prototype.imulK = function(e) {
			e.words[e.length] = 0, e.words[e.length + 1] = 0, e.length += 2;
			for (var t = 0, n = 0; n < e.length; n++) {
				var r = e.words[n] | 0;
				t += r * 977, e.words[n] = t & 67108863, t = r * 64 + (t / 67108864 | 0);
			}
			return e.words[e.length - 1] === 0 && (e.length--, e.words[e.length - 1] === 0 && e.length--), e;
		};
		function x() {
			y.call(this, "p224", "ffffffff ffffffff ffffffff ffffffff 00000000 00000000 00000001");
		}
		r(x, y);
		function S() {
			y.call(this, "p192", "ffffffff ffffffff ffffffff fffffffe ffffffff ffffffff");
		}
		r(S, y);
		function C() {
			y.call(this, "25519", "7fffffffffffffff ffffffffffffffff ffffffffffffffff ffffffffffffffed");
		}
		r(C, y), C.prototype.imulK = function(e) {
			for (var t = 0, n = 0; n < e.length; n++) {
				var r = (e.words[n] | 0) * 19 + t, i = r & 67108863;
				r >>>= 26, e.words[n] = i, t = r;
			}
			return t !== 0 && (e.words[e.length++] = t), e;
		}, i._prime = function(e) {
			if (v[e]) return v[e];
			var t;
			if (e === "k256") t = new b();
			else if (e === "p224") t = new x();
			else if (e === "p192") t = new S();
			else if (e === "p25519") t = new C();
			else throw Error("Unknown prime " + e);
			return v[e] = t, t;
		};
		function w(e) {
			if (typeof e == "string") {
				var t = i._prime(e);
				this.m = t.p, this.prime = t;
			} else n(e.gtn(1), "modulus must be greater than 1"), this.m = e, this.prime = null;
		}
		w.prototype._verify1 = function(e) {
			n(e.negative === 0, "red works only with positives"), n(e.red, "red works only with red numbers");
		}, w.prototype._verify2 = function(e, t) {
			n((e.negative | t.negative) === 0, "red works only with positives"), n(e.red && e.red === t.red, "red works only with red numbers");
		}, w.prototype.imod = function(e) {
			return this.prime ? this.prime.ireduce(e)._forceRed(this) : e.umod(this.m)._forceRed(this);
		}, w.prototype.neg = function(e) {
			return e.isZero() ? e.clone() : this.m.sub(e)._forceRed(this);
		}, w.prototype.add = function(e, t) {
			this._verify2(e, t);
			var n = e.add(t);
			return n.cmp(this.m) >= 0 && n.isub(this.m), n._forceRed(this);
		}, w.prototype.iadd = function(e, t) {
			this._verify2(e, t);
			var n = e.iadd(t);
			return n.cmp(this.m) >= 0 && n.isub(this.m), n;
		}, w.prototype.sub = function(e, t) {
			this._verify2(e, t);
			var n = e.sub(t);
			return n.cmpn(0) < 0 && n.iadd(this.m), n._forceRed(this);
		}, w.prototype.isub = function(e, t) {
			this._verify2(e, t);
			var n = e.isub(t);
			return n.cmpn(0) < 0 && n.iadd(this.m), n;
		}, w.prototype.shl = function(e, t) {
			return this._verify1(e), this.imod(e.ushln(t));
		}, w.prototype.imul = function(e, t) {
			return this._verify2(e, t), this.imod(e.imul(t));
		}, w.prototype.mul = function(e, t) {
			return this._verify2(e, t), this.imod(e.mul(t));
		}, w.prototype.isqr = function(e) {
			return this.imul(e, e.clone());
		}, w.prototype.sqr = function(e) {
			return this.mul(e, e);
		}, w.prototype.sqrt = function(e) {
			if (e.isZero()) return e.clone();
			var t = this.m.andln(3);
			if (n(t % 2 == 1), t === 3) {
				var r = this.m.add(new i(1)).iushrn(2);
				return this.pow(e, r);
			}
			for (var a = this.m.subn(1), o = 0; !a.isZero() && a.andln(1) === 0;) o++, a.iushrn(1);
			n(!a.isZero());
			var s = new i(1).toRed(this), c = s.redNeg(), l = this.m.subn(1).iushrn(1), u = this.m.bitLength();
			for (u = new i(2 * u * u).toRed(this); this.pow(u, l).cmp(c) !== 0;) u.redIAdd(c);
			for (var d = this.pow(u, a), f = this.pow(e, a.addn(1).iushrn(1)), p = this.pow(e, a), m = o; p.cmp(s) !== 0;) {
				for (var h = p, g = 0; h.cmp(s) !== 0; g++) h = h.redSqr();
				n(g < m);
				var _ = this.pow(d, new i(1).iushln(m - g - 1));
				f = f.redMul(_), d = _.redSqr(), p = p.redMul(d), m = g;
			}
			return f;
		}, w.prototype.invm = function(e) {
			var t = e._invmp(this.m);
			return t.negative === 0 ? this.imod(t) : (t.negative = 0, this.imod(t).redNeg());
		}, w.prototype.pow = function(e, t) {
			if (t.isZero()) return new i(1).toRed(this);
			if (t.cmpn(1) === 0) return e.clone();
			var n = 4, r = Array(1 << n);
			r[0] = new i(1).toRed(this), r[1] = e;
			for (var a = 2; a < r.length; a++) r[a] = this.mul(r[a - 1], e);
			var o = r[0], s = 0, c = 0, l = t.bitLength() % 26;
			for (l === 0 && (l = 26), a = t.length - 1; a >= 0; a--) {
				for (var u = t.words[a], d = l - 1; d >= 0; d--) {
					var f = u >> d & 1;
					if (o !== r[0] && (o = this.sqr(o)), f === 0 && s === 0) {
						c = 0;
						continue;
					}
					s <<= 1, s |= f, c++, !(c !== n && (a !== 0 || d !== 0)) && (o = this.mul(o, r[s]), c = 0, s = 0);
				}
				l = 26;
			}
			return o;
		}, w.prototype.convertTo = function(e) {
			var t = e.umod(this.m);
			return t === e ? t.clone() : t;
		}, w.prototype.convertFrom = function(e) {
			var t = e.clone();
			return t.red = null, t;
		}, i.mont = function(e) {
			return new T(e);
		};
		function T(e) {
			w.call(this, e), this.shift = this.m.bitLength(), this.shift % 26 != 0 && (this.shift += 26 - this.shift % 26), this.r = new i(1).iushln(this.shift), this.r2 = this.imod(this.r.sqr()), this.rinv = this.r._invmp(this.m), this.minv = this.rinv.mul(this.r).isubn(1).div(this.m), this.minv = this.minv.umod(this.r), this.minv = this.r.sub(this.minv);
		}
		r(T, w), T.prototype.convertTo = function(e) {
			return this.imod(e.ushln(this.shift));
		}, T.prototype.convertFrom = function(e) {
			var t = this.imod(e.mul(this.rinv));
			return t.red = null, t;
		}, T.prototype.imul = function(e, t) {
			if (e.isZero() || t.isZero()) return e.words[0] = 0, e.length = 1, e;
			var n = e.imul(t), r = n.maskn(this.shift).mul(this.minv).imaskn(this.shift).mul(this.m), i = n.isub(r).iushrn(this.shift), a = i;
			return i.cmp(this.m) >= 0 ? a = i.isub(this.m) : i.cmpn(0) < 0 && (a = i.iadd(this.m)), a._forceRed(this);
		}, T.prototype.mul = function(e, t) {
			if (e.isZero() || t.isZero()) return new i(0)._forceRed(this);
			var n = e.mul(t), r = n.maskn(this.shift).mul(this.minv).imaskn(this.shift).mul(this.m), a = n.isub(r).iushrn(this.shift), o = a;
			return a.cmp(this.m) >= 0 ? o = a.isub(this.m) : a.cmpn(0) < 0 && (o = a.iadd(this.m)), o._forceRed(this);
		}, T.prototype.invm = function(e) {
			return this.imod(e._invmp(this.m).mul(this.r2))._forceRed(this);
		};
	})(t === void 0 || t, e);
})), us = /* @__PURE__ */ s(((e, t) => {
	t.exports = n;
	function n(e, t) {
		if (!e) throw Error(t || "Assertion failed");
	}
	n.equal = function(e, t, n) {
		if (e != t) throw Error(n || "Assertion failed: " + e + " != " + t);
	};
})), ds = /* @__PURE__ */ s(((e) => {
	var t = e;
	function n(e, t) {
		if (Array.isArray(e)) return e.slice();
		if (!e) return [];
		var n = [];
		if (typeof e != "string") {
			for (var r = 0; r < e.length; r++) n[r] = e[r] | 0;
			return n;
		}
		if (t === "hex") {
			e = e.replace(/[^a-z0-9]+/gi, ""), e.length % 2 != 0 && (e = "0" + e);
			for (var r = 0; r < e.length; r += 2) n.push(parseInt(e[r] + e[r + 1], 16));
		} else for (var r = 0; r < e.length; r++) {
			var i = e.charCodeAt(r), a = i >> 8, o = i & 255;
			a ? n.push(a, o) : n.push(o);
		}
		return n;
	}
	t.toArray = n;
	function r(e) {
		return e.length === 1 ? "0" + e : e;
	}
	t.zero2 = r;
	function i(e) {
		for (var t = "", n = 0; n < e.length; n++) t += r(e[n].toString(16));
		return t;
	}
	t.toHex = i, t.encode = function(e, t) {
		return t === "hex" ? i(e) : e;
	};
})), fs = /* @__PURE__ */ s(((e) => {
	var t = e, n = ls(), r = us(), i = ds();
	t.assert = r, t.toArray = i.toArray, t.zero2 = i.zero2, t.toHex = i.toHex, t.encode = i.encode;
	function a(e, t, n) {
		var r = Array(Math.max(e.bitLength(), n) + 1), i;
		for (i = 0; i < r.length; i += 1) r[i] = 0;
		var a = 1 << t + 1, o = e.clone();
		for (i = 0; i < r.length; i++) {
			var s, c = o.andln(a - 1);
			o.isOdd() ? (s = c > (a >> 1) - 1 ? (a >> 1) - c : c, o.isubn(s)) : s = 0, r[i] = s, o.iushrn(1);
		}
		return r;
	}
	t.getNAF = a;
	function o(e, t) {
		var n = [[], []];
		e = e.clone(), t = t.clone();
		for (var r = 0, i = 0, a; e.cmpn(-r) > 0 || t.cmpn(-i) > 0;) {
			var o = e.andln(3) + r & 3, s = t.andln(3) + i & 3;
			o === 3 && (o = -1), s === 3 && (s = -1);
			var c;
			o & 1 ? (a = e.andln(7) + r & 7, c = (a === 3 || a === 5) && s === 2 ? -o : o) : c = 0, n[0].push(c);
			var l;
			s & 1 ? (a = t.andln(7) + i & 7, l = (a === 3 || a === 5) && o === 2 ? -s : s) : l = 0, n[1].push(l), 2 * r === c + 1 && (r = 1 - r), 2 * i === l + 1 && (i = 1 - i), e.iushrn(1), t.iushrn(1);
		}
		return n;
	}
	t.getJSF = o;
	function s(e, t, n) {
		var r = "_" + t;
		e.prototype[t] = function() {
			return this[r] === void 0 ? this[r] = n.call(this) : this[r];
		};
	}
	t.cachedProperty = s;
	function c(e) {
		return typeof e == "string" ? t.toArray(e, "hex") : e;
	}
	t.parseBytes = c;
	function l(e) {
		return new n(e, "hex", "le");
	}
	t.intFromLE = l;
})), ps = /* @__PURE__ */ s(((e, t) => {
	var n;
	t.exports = function(e) {
		return n ||= new r(null), n.generate(e);
	};
	function r(e) {
		this.rand = e;
	}
	if (t.exports.Rand = r, r.prototype.generate = function(e) {
		return this._rand(e);
	}, r.prototype._rand = function(e) {
		if (this.rand.getBytes) return this.rand.getBytes(e);
		for (var t = new Uint8Array(e), n = 0; n < t.length; n++) t[n] = this.rand.getByte();
		return t;
	}, typeof self == "object") self.crypto && self.crypto.getRandomValues ? r.prototype._rand = function(e) {
		var t = new Uint8Array(e);
		return self.crypto.getRandomValues(t), t;
	} : self.msCrypto && self.msCrypto.getRandomValues ? r.prototype._rand = function(e) {
		var t = new Uint8Array(e);
		return self.msCrypto.getRandomValues(t), t;
	} : typeof window == "object" && (r.prototype._rand = function() {
		throw Error("Not implemented yet");
	});
	else try {
		var i = cs();
		if (typeof i.randomBytes != "function") throw Error("Not supported");
		r.prototype._rand = function(e) {
			return i.randomBytes(e);
		};
	} catch {}
})), ms = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = fs(), i = r.getNAF, a = r.getJSF, o = r.assert;
	function s(e, t) {
		this.type = e, this.p = new n(t.p, 16), this.red = t.prime ? n.red(t.prime) : n.mont(this.p), this.zero = new n(0).toRed(this.red), this.one = new n(1).toRed(this.red), this.two = new n(2).toRed(this.red), this.n = t.n && new n(t.n, 16), this.g = t.g && this.pointFromJSON(t.g, t.gRed), this._wnafT1 = [
			,
			,
			,
			,
		], this._wnafT2 = [
			,
			,
			,
			,
		], this._wnafT3 = [
			,
			,
			,
			,
		], this._wnafT4 = [
			,
			,
			,
			,
		], this._bitLength = this.n ? this.n.bitLength() : 0;
		var r = this.n && this.p.div(this.n);
		!r || r.cmpn(100) > 0 ? this.redN = null : (this._maxwellTrick = !0, this.redN = this.n.toRed(this.red));
	}
	t.exports = s, s.prototype.point = function() {
		throw Error("Not implemented");
	}, s.prototype.validate = function() {
		throw Error("Not implemented");
	}, s.prototype._fixedNafMul = function(e, t) {
		o(e.precomputed);
		var n = e._getDoubles(), r = i(t, 1, this._bitLength), a = (1 << n.step + 1) - (n.step % 2 == 0 ? 2 : 1);
		a /= 3;
		var s = [], c, l;
		for (c = 0; c < r.length; c += n.step) {
			l = 0;
			for (var u = c + n.step - 1; u >= c; u--) l = (l << 1) + r[u];
			s.push(l);
		}
		for (var d = this.jpoint(null, null, null), f = this.jpoint(null, null, null), p = a; p > 0; p--) {
			for (c = 0; c < s.length; c++) l = s[c], l === p ? f = f.mixedAdd(n.points[c]) : l === -p && (f = f.mixedAdd(n.points[c].neg()));
			d = d.add(f);
		}
		return d.toP();
	}, s.prototype._wnafMul = function(e, t) {
		var n = 4, r = e._getNAFPoints(n);
		n = r.wnd;
		for (var a = r.points, s = i(t, n, this._bitLength), c = this.jpoint(null, null, null), l = s.length - 1; l >= 0; l--) {
			for (var u = 0; l >= 0 && s[l] === 0; l--) u++;
			if (l >= 0 && u++, c = c.dblp(u), l < 0) break;
			var d = s[l];
			o(d !== 0), c = e.type === "affine" ? d > 0 ? c.mixedAdd(a[d - 1 >> 1]) : c.mixedAdd(a[-d - 1 >> 1].neg()) : d > 0 ? c.add(a[d - 1 >> 1]) : c.add(a[-d - 1 >> 1].neg());
		}
		return e.type === "affine" ? c.toP() : c;
	}, s.prototype._wnafMulAdd = function(e, t, n, r, o) {
		var s = this._wnafT1, c = this._wnafT2, l = this._wnafT3, u = 0, d, f, p;
		for (d = 0; d < r; d++) {
			p = t[d];
			var m = p._getNAFPoints(e);
			s[d] = m.wnd, c[d] = m.points;
		}
		for (d = r - 1; d >= 1; d -= 2) {
			var h = d - 1, g = d;
			if (s[h] !== 1 || s[g] !== 1) {
				l[h] = i(n[h], s[h], this._bitLength), l[g] = i(n[g], s[g], this._bitLength), u = Math.max(l[h].length, u), u = Math.max(l[g].length, u);
				continue;
			}
			var _ = [
				t[h],
				null,
				null,
				t[g]
			];
			t[h].y.cmp(t[g].y) === 0 ? (_[1] = t[h].add(t[g]), _[2] = t[h].toJ().mixedAdd(t[g].neg())) : t[h].y.cmp(t[g].y.redNeg()) === 0 ? (_[1] = t[h].toJ().mixedAdd(t[g]), _[2] = t[h].add(t[g].neg())) : (_[1] = t[h].toJ().mixedAdd(t[g]), _[2] = t[h].toJ().mixedAdd(t[g].neg()));
			var v = [
				-3,
				-1,
				-5,
				-7,
				0,
				7,
				5,
				1,
				3
			], y = a(n[h], n[g]);
			for (u = Math.max(y[0].length, u), l[h] = Array(u), l[g] = Array(u), f = 0; f < u; f++) {
				var b = y[0][f] | 0, x = y[1][f] | 0;
				l[h][f] = v[(b + 1) * 3 + (x + 1)], l[g][f] = 0, c[h] = _;
			}
		}
		var S = this.jpoint(null, null, null), C = this._wnafT4;
		for (d = u; d >= 0; d--) {
			for (var w = 0; d >= 0;) {
				var T = !0;
				for (f = 0; f < r; f++) C[f] = l[f][d] | 0, C[f] !== 0 && (T = !1);
				if (!T) break;
				w++, d--;
			}
			if (d >= 0 && w++, S = S.dblp(w), d < 0) break;
			for (f = 0; f < r; f++) {
				var E = C[f];
				E !== 0 && (E > 0 ? p = c[f][E - 1 >> 1] : E < 0 && (p = c[f][-E - 1 >> 1].neg()), S = p.type === "affine" ? S.mixedAdd(p) : S.add(p));
			}
		}
		for (d = 0; d < r; d++) c[d] = null;
		return o ? S : S.toP();
	};
	function c(e, t) {
		this.curve = e, this.type = t, this.precomputed = null;
	}
	s.BasePoint = c, c.prototype.eq = function() {
		throw Error("Not implemented");
	}, c.prototype.validate = function() {
		return this.curve.validate(this);
	}, s.prototype.decodePoint = function(e, t) {
		e = r.toArray(e, t);
		var n = this.p.byteLength();
		if ((e[0] === 4 || e[0] === 6 || e[0] === 7) && e.length - 1 == 2 * n) return e[0] === 6 ? o(e[e.length - 1] % 2 == 0) : e[0] === 7 && o(e[e.length - 1] % 2 == 1), this.point(e.slice(1, 1 + n), e.slice(1 + n, 1 + 2 * n));
		if ((e[0] === 2 || e[0] === 3) && e.length - 1 === n) return this.pointFromX(e.slice(1, 1 + n), e[0] === 3);
		throw Error("Unknown point format");
	}, c.prototype.encodeCompressed = function(e) {
		return this.encode(e, !0);
	}, c.prototype._encode = function(e) {
		var t = this.curve.p.byteLength(), n = this.getX().toArray("be", t);
		return e ? [this.getY().isEven() ? 2 : 3].concat(n) : [4].concat(n, this.getY().toArray("be", t));
	}, c.prototype.encode = function(e, t) {
		return r.encode(this._encode(t), e);
	}, c.prototype.precompute = function(e) {
		if (this.precomputed) return this;
		var t = {
			doubles: null,
			naf: null,
			beta: null
		};
		return t.naf = this._getNAFPoints(8), t.doubles = this._getDoubles(4, e), t.beta = this._getBeta(), this.precomputed = t, this;
	}, c.prototype._hasDoubles = function(e) {
		if (!this.precomputed) return !1;
		var t = this.precomputed.doubles;
		return t ? t.points.length >= Math.ceil((e.bitLength() + 1) / t.step) : !1;
	}, c.prototype._getDoubles = function(e, t) {
		if (this.precomputed && this.precomputed.doubles) return this.precomputed.doubles;
		for (var n = [this], r = this, i = 0; i < t; i += e) {
			for (var a = 0; a < e; a++) r = r.dbl();
			n.push(r);
		}
		return {
			step: e,
			points: n
		};
	}, c.prototype._getNAFPoints = function(e) {
		if (this.precomputed && this.precomputed.naf) return this.precomputed.naf;
		for (var t = [this], n = (1 << e) - 1, r = n === 1 ? null : this.dbl(), i = 1; i < n; i++) t[i] = t[i - 1].add(r);
		return {
			wnd: e,
			points: t
		};
	}, c.prototype._getBeta = function() {
		return null;
	}, c.prototype.dblp = function(e) {
		for (var t = this, n = 0; n < e; n++) t = t.dbl();
		return t;
	};
})), hs = /* @__PURE__ */ s(((e, t) => {
	typeof Object.create == "function" ? t.exports = function(e, t) {
		t && (e.super_ = t, e.prototype = Object.create(t.prototype, { constructor: {
			value: e,
			enumerable: !1,
			writable: !0,
			configurable: !0
		} }));
	} : t.exports = function(e, t) {
		if (t) {
			e.super_ = t;
			var n = function() {};
			n.prototype = t.prototype, e.prototype = new n(), e.prototype.constructor = e;
		}
	};
})), gs = /* @__PURE__ */ s(((e, t) => {
	var n = fs(), r = ls(), i = hs(), a = ms(), o = n.assert;
	function s(e) {
		a.call(this, "short", e), this.a = new r(e.a, 16).toRed(this.red), this.b = new r(e.b, 16).toRed(this.red), this.tinv = this.two.redInvm(), this.zeroA = this.a.fromRed().cmpn(0) === 0, this.threeA = this.a.fromRed().sub(this.p).cmpn(-3) === 0, this.endo = this._getEndomorphism(e), this._endoWnafT1 = [
			,
			,
			,
			,
		], this._endoWnafT2 = [
			,
			,
			,
			,
		];
	}
	i(s, a), t.exports = s, s.prototype._getEndomorphism = function(e) {
		if (!(!this.zeroA || !this.g || !this.n || this.p.modn(3) !== 1)) {
			var t, n;
			if (e.beta) t = new r(e.beta, 16).toRed(this.red);
			else {
				var i = this._getEndoRoots(this.p);
				t = i[0].cmp(i[1]) < 0 ? i[0] : i[1], t = t.toRed(this.red);
			}
			if (e.lambda) n = new r(e.lambda, 16);
			else {
				var a = this._getEndoRoots(this.n);
				this.g.mul(a[0]).x.cmp(this.g.x.redMul(t)) === 0 ? n = a[0] : (n = a[1], o(this.g.mul(n).x.cmp(this.g.x.redMul(t)) === 0));
			}
			var s = e.basis ? e.basis.map(function(e) {
				return {
					a: new r(e.a, 16),
					b: new r(e.b, 16)
				};
			}) : this._getEndoBasis(n);
			return {
				beta: t,
				lambda: n,
				basis: s
			};
		}
	}, s.prototype._getEndoRoots = function(e) {
		var t = e === this.p ? this.red : r.mont(e), n = new r(2).toRed(t).redInvm(), i = n.redNeg(), a = new r(3).toRed(t).redNeg().redSqrt().redMul(n);
		return [i.redAdd(a).fromRed(), i.redSub(a).fromRed()];
	}, s.prototype._getEndoBasis = function(e) {
		for (var t = this.n.ushrn(Math.floor(this.n.bitLength() / 2)), n = e, i = this.n.clone(), a = new r(1), o = new r(0), s = new r(0), c = new r(1), l, u, d, f, p, m, h, g = 0, _, v; n.cmpn(0) !== 0;) {
			var y = i.div(n);
			_ = i.sub(y.mul(n)), v = s.sub(y.mul(a));
			var b = c.sub(y.mul(o));
			if (!d && _.cmp(t) < 0) l = h.neg(), u = a, d = _.neg(), f = v;
			else if (d && ++g === 2) break;
			h = _, i = n, n = _, s = a, a = v, c = o, o = b;
		}
		p = _.neg(), m = v;
		var x = d.sqr().add(f.sqr());
		return p.sqr().add(m.sqr()).cmp(x) >= 0 && (p = l, m = u), d.negative && (d = d.neg(), f = f.neg()), p.negative && (p = p.neg(), m = m.neg()), [{
			a: d,
			b: f
		}, {
			a: p,
			b: m
		}];
	}, s.prototype._endoSplit = function(e) {
		var t = this.endo.basis, n = t[0], r = t[1], i = r.b.mul(e).divRound(this.n), a = n.b.neg().mul(e).divRound(this.n), o = i.mul(n.a), s = a.mul(r.a), c = i.mul(n.b), l = a.mul(r.b);
		return {
			k1: e.sub(o).sub(s),
			k2: c.add(l).neg()
		};
	}, s.prototype.pointFromX = function(e, t) {
		e = new r(e, 16), e.red || (e = e.toRed(this.red));
		var n = e.redSqr().redMul(e).redIAdd(e.redMul(this.a)).redIAdd(this.b), i = n.redSqrt();
		if (i.redSqr().redSub(n).cmp(this.zero) !== 0) throw Error("invalid point");
		var a = i.fromRed().isOdd();
		return (t && !a || !t && a) && (i = i.redNeg()), this.point(e, i);
	}, s.prototype.validate = function(e) {
		if (e.inf) return !0;
		var t = e.x, n = e.y, r = this.a.redMul(t), i = t.redSqr().redMul(t).redIAdd(r).redIAdd(this.b);
		return n.redSqr().redISub(i).cmpn(0) === 0;
	}, s.prototype._endoWnafMulAdd = function(e, t, n) {
		for (var r = this._endoWnafT1, i = this._endoWnafT2, a = 0; a < e.length; a++) {
			var o = this._endoSplit(t[a]), s = e[a], c = s._getBeta();
			o.k1.negative && (o.k1.ineg(), s = s.neg(!0)), o.k2.negative && (o.k2.ineg(), c = c.neg(!0)), r[a * 2] = s, r[a * 2 + 1] = c, i[a * 2] = o.k1, i[a * 2 + 1] = o.k2;
		}
		for (var l = this._wnafMulAdd(1, r, i, a * 2, n), u = 0; u < a * 2; u++) r[u] = null, i[u] = null;
		return l;
	};
	function c(e, t, n, i) {
		a.BasePoint.call(this, e, "affine"), t === null && n === null ? (this.x = null, this.y = null, this.inf = !0) : (this.x = new r(t, 16), this.y = new r(n, 16), i && (this.x.forceRed(this.curve.red), this.y.forceRed(this.curve.red)), this.x.red || (this.x = this.x.toRed(this.curve.red)), this.y.red || (this.y = this.y.toRed(this.curve.red)), this.inf = !1);
	}
	i(c, a.BasePoint), s.prototype.point = function(e, t, n) {
		return new c(this, e, t, n);
	}, s.prototype.pointFromJSON = function(e, t) {
		return c.fromJSON(this, e, t);
	}, c.prototype._getBeta = function() {
		if (this.curve.endo) {
			var e = this.precomputed;
			if (e && e.beta) return e.beta;
			var t = this.curve.point(this.x.redMul(this.curve.endo.beta), this.y);
			if (e) {
				var n = this.curve, r = function(e) {
					return n.point(e.x.redMul(n.endo.beta), e.y);
				};
				e.beta = t, t.precomputed = {
					beta: null,
					naf: e.naf && {
						wnd: e.naf.wnd,
						points: e.naf.points.map(r)
					},
					doubles: e.doubles && {
						step: e.doubles.step,
						points: e.doubles.points.map(r)
					}
				};
			}
			return t;
		}
	}, c.prototype.toJSON = function() {
		return this.precomputed ? [
			this.x,
			this.y,
			this.precomputed && {
				doubles: this.precomputed.doubles && {
					step: this.precomputed.doubles.step,
					points: this.precomputed.doubles.points.slice(1)
				},
				naf: this.precomputed.naf && {
					wnd: this.precomputed.naf.wnd,
					points: this.precomputed.naf.points.slice(1)
				}
			}
		] : [this.x, this.y];
	}, c.fromJSON = function(e, t, n) {
		typeof t == "string" && (t = JSON.parse(t));
		var r = e.point(t[0], t[1], n);
		if (!t[2]) return r;
		function i(t) {
			return e.point(t[0], t[1], n);
		}
		var a = t[2];
		return r.precomputed = {
			beta: null,
			doubles: a.doubles && {
				step: a.doubles.step,
				points: [r].concat(a.doubles.points.map(i))
			},
			naf: a.naf && {
				wnd: a.naf.wnd,
				points: [r].concat(a.naf.points.map(i))
			}
		}, r;
	}, c.prototype.inspect = function() {
		return this.isInfinity() ? "<EC Point Infinity>" : "<EC Point x: " + this.x.fromRed().toString(16, 2) + " y: " + this.y.fromRed().toString(16, 2) + ">";
	}, c.prototype.isInfinity = function() {
		return this.inf;
	}, c.prototype.add = function(e) {
		if (this.inf) return e;
		if (e.inf) return this;
		if (this.eq(e)) return this.dbl();
		if (this.neg().eq(e) || this.x.cmp(e.x) === 0) return this.curve.point(null, null);
		var t = this.y.redSub(e.y);
		t.cmpn(0) !== 0 && (t = t.redMul(this.x.redSub(e.x).redInvm()));
		var n = t.redSqr().redISub(this.x).redISub(e.x), r = t.redMul(this.x.redSub(n)).redISub(this.y);
		return this.curve.point(n, r);
	}, c.prototype.dbl = function() {
		if (this.inf) return this;
		var e = this.y.redAdd(this.y);
		if (e.cmpn(0) === 0) return this.curve.point(null, null);
		var t = this.curve.a, n = this.x.redSqr(), r = e.redInvm(), i = n.redAdd(n).redIAdd(n).redIAdd(t).redMul(r), a = i.redSqr().redISub(this.x.redAdd(this.x)), o = i.redMul(this.x.redSub(a)).redISub(this.y);
		return this.curve.point(a, o);
	}, c.prototype.getX = function() {
		return this.x.fromRed();
	}, c.prototype.getY = function() {
		return this.y.fromRed();
	}, c.prototype.mul = function(e) {
		return e = new r(e, 16), this.isInfinity() ? this : this._hasDoubles(e) ? this.curve._fixedNafMul(this, e) : this.curve.endo ? this.curve._endoWnafMulAdd([this], [e]) : this.curve._wnafMul(this, e);
	}, c.prototype.mulAdd = function(e, t, n) {
		var r = [this, t], i = [e, n];
		return this.curve.endo ? this.curve._endoWnafMulAdd(r, i) : this.curve._wnafMulAdd(1, r, i, 2);
	}, c.prototype.jmulAdd = function(e, t, n) {
		var r = [this, t], i = [e, n];
		return this.curve.endo ? this.curve._endoWnafMulAdd(r, i, !0) : this.curve._wnafMulAdd(1, r, i, 2, !0);
	}, c.prototype.eq = function(e) {
		return this === e || this.inf === e.inf && (this.inf || this.x.cmp(e.x) === 0 && this.y.cmp(e.y) === 0);
	}, c.prototype.neg = function(e) {
		if (this.inf) return this;
		var t = this.curve.point(this.x, this.y.redNeg());
		if (e && this.precomputed) {
			var n = this.precomputed, r = function(e) {
				return e.neg();
			};
			t.precomputed = {
				naf: n.naf && {
					wnd: n.naf.wnd,
					points: n.naf.points.map(r)
				},
				doubles: n.doubles && {
					step: n.doubles.step,
					points: n.doubles.points.map(r)
				}
			};
		}
		return t;
	}, c.prototype.toJ = function() {
		return this.inf ? this.curve.jpoint(null, null, null) : this.curve.jpoint(this.x, this.y, this.curve.one);
	};
	function l(e, t, n, i) {
		a.BasePoint.call(this, e, "jacobian"), t === null && n === null && i === null ? (this.x = this.curve.one, this.y = this.curve.one, this.z = new r(0)) : (this.x = new r(t, 16), this.y = new r(n, 16), this.z = new r(i, 16)), this.x.red || (this.x = this.x.toRed(this.curve.red)), this.y.red || (this.y = this.y.toRed(this.curve.red)), this.z.red || (this.z = this.z.toRed(this.curve.red)), this.zOne = this.z === this.curve.one;
	}
	i(l, a.BasePoint), s.prototype.jpoint = function(e, t, n) {
		return new l(this, e, t, n);
	}, l.prototype.toP = function() {
		if (this.isInfinity()) return this.curve.point(null, null);
		var e = this.z.redInvm(), t = e.redSqr(), n = this.x.redMul(t), r = this.y.redMul(t).redMul(e);
		return this.curve.point(n, r);
	}, l.prototype.neg = function() {
		return this.curve.jpoint(this.x, this.y.redNeg(), this.z);
	}, l.prototype.add = function(e) {
		if (this.isInfinity()) return e;
		if (e.isInfinity()) return this;
		var t = e.z.redSqr(), n = this.z.redSqr(), r = this.x.redMul(t), i = e.x.redMul(n), a = this.y.redMul(t.redMul(e.z)), o = e.y.redMul(n.redMul(this.z)), s = r.redSub(i), c = a.redSub(o);
		if (s.cmpn(0) === 0) return c.cmpn(0) === 0 ? this.dbl() : this.curve.jpoint(null, null, null);
		var l = s.redSqr(), u = l.redMul(s), d = r.redMul(l), f = c.redSqr().redIAdd(u).redISub(d).redISub(d), p = c.redMul(d.redISub(f)).redISub(a.redMul(u)), m = this.z.redMul(e.z).redMul(s);
		return this.curve.jpoint(f, p, m);
	}, l.prototype.mixedAdd = function(e) {
		if (this.isInfinity()) return e.toJ();
		if (e.isInfinity()) return this;
		var t = this.z.redSqr(), n = this.x, r = e.x.redMul(t), i = this.y, a = e.y.redMul(t).redMul(this.z), o = n.redSub(r), s = i.redSub(a);
		if (o.cmpn(0) === 0) return s.cmpn(0) === 0 ? this.dbl() : this.curve.jpoint(null, null, null);
		var c = o.redSqr(), l = c.redMul(o), u = n.redMul(c), d = s.redSqr().redIAdd(l).redISub(u).redISub(u), f = s.redMul(u.redISub(d)).redISub(i.redMul(l)), p = this.z.redMul(o);
		return this.curve.jpoint(d, f, p);
	}, l.prototype.dblp = function(e) {
		if (e === 0 || this.isInfinity()) return this;
		if (!e) return this.dbl();
		var t;
		if (this.curve.zeroA || this.curve.threeA) {
			var n = this;
			for (t = 0; t < e; t++) n = n.dbl();
			return n;
		}
		var r = this.curve.a, i = this.curve.tinv, a = this.x, o = this.y, s = this.z, c = s.redSqr().redSqr(), l = o.redAdd(o);
		for (t = 0; t < e; t++) {
			var u = a.redSqr(), d = l.redSqr(), f = d.redSqr(), p = u.redAdd(u).redIAdd(u).redIAdd(r.redMul(c)), m = a.redMul(d), h = p.redSqr().redISub(m.redAdd(m)), g = m.redISub(h), _ = p.redMul(g);
			_ = _.redIAdd(_).redISub(f);
			var v = l.redMul(s);
			t + 1 < e && (c = c.redMul(f)), a = h, s = v, l = _;
		}
		return this.curve.jpoint(a, l.redMul(i), s);
	}, l.prototype.dbl = function() {
		return this.isInfinity() ? this : this.curve.zeroA ? this._zeroDbl() : this.curve.threeA ? this._threeDbl() : this._dbl();
	}, l.prototype._zeroDbl = function() {
		var e, t, n;
		if (this.zOne) {
			var r = this.x.redSqr(), i = this.y.redSqr(), a = i.redSqr(), o = this.x.redAdd(i).redSqr().redISub(r).redISub(a);
			o = o.redIAdd(o);
			var s = r.redAdd(r).redIAdd(r), c = s.redSqr().redISub(o).redISub(o), l = a.redIAdd(a);
			l = l.redIAdd(l), l = l.redIAdd(l), e = c, t = s.redMul(o.redISub(c)).redISub(l), n = this.y.redAdd(this.y);
		} else {
			var u = this.x.redSqr(), d = this.y.redSqr(), f = d.redSqr(), p = this.x.redAdd(d).redSqr().redISub(u).redISub(f);
			p = p.redIAdd(p);
			var m = u.redAdd(u).redIAdd(u), h = m.redSqr(), g = f.redIAdd(f);
			g = g.redIAdd(g), g = g.redIAdd(g), e = h.redISub(p).redISub(p), t = m.redMul(p.redISub(e)).redISub(g), n = this.y.redMul(this.z), n = n.redIAdd(n);
		}
		return this.curve.jpoint(e, t, n);
	}, l.prototype._threeDbl = function() {
		var e, t, n;
		if (this.zOne) {
			var r = this.x.redSqr(), i = this.y.redSqr(), a = i.redSqr(), o = this.x.redAdd(i).redSqr().redISub(r).redISub(a);
			o = o.redIAdd(o);
			var s = r.redAdd(r).redIAdd(r).redIAdd(this.curve.a), c = s.redSqr().redISub(o).redISub(o);
			e = c;
			var l = a.redIAdd(a);
			l = l.redIAdd(l), l = l.redIAdd(l), t = s.redMul(o.redISub(c)).redISub(l), n = this.y.redAdd(this.y);
		} else {
			var u = this.z.redSqr(), d = this.y.redSqr(), f = this.x.redMul(d), p = this.x.redSub(u).redMul(this.x.redAdd(u));
			p = p.redAdd(p).redIAdd(p);
			var m = f.redIAdd(f);
			m = m.redIAdd(m);
			var h = m.redAdd(m);
			e = p.redSqr().redISub(h), n = this.y.redAdd(this.z).redSqr().redISub(d).redISub(u);
			var g = d.redSqr();
			g = g.redIAdd(g), g = g.redIAdd(g), g = g.redIAdd(g), t = p.redMul(m.redISub(e)).redISub(g);
		}
		return this.curve.jpoint(e, t, n);
	}, l.prototype._dbl = function() {
		var e = this.curve.a, t = this.x, n = this.y, r = this.z, i = r.redSqr().redSqr(), a = t.redSqr(), o = n.redSqr(), s = a.redAdd(a).redIAdd(a).redIAdd(e.redMul(i)), c = t.redAdd(t);
		c = c.redIAdd(c);
		var l = c.redMul(o), u = s.redSqr().redISub(l.redAdd(l)), d = l.redISub(u), f = o.redSqr();
		f = f.redIAdd(f), f = f.redIAdd(f), f = f.redIAdd(f);
		var p = s.redMul(d).redISub(f), m = n.redAdd(n).redMul(r);
		return this.curve.jpoint(u, p, m);
	}, l.prototype.trpl = function() {
		if (!this.curve.zeroA) return this.dbl().add(this);
		var e = this.x.redSqr(), t = this.y.redSqr(), n = this.z.redSqr(), r = t.redSqr(), i = e.redAdd(e).redIAdd(e), a = i.redSqr(), o = this.x.redAdd(t).redSqr().redISub(e).redISub(r);
		o = o.redIAdd(o), o = o.redAdd(o).redIAdd(o), o = o.redISub(a);
		var s = o.redSqr(), c = r.redIAdd(r);
		c = c.redIAdd(c), c = c.redIAdd(c), c = c.redIAdd(c);
		var l = i.redIAdd(o).redSqr().redISub(a).redISub(s).redISub(c), u = t.redMul(l);
		u = u.redIAdd(u), u = u.redIAdd(u);
		var d = this.x.redMul(s).redISub(u);
		d = d.redIAdd(d), d = d.redIAdd(d);
		var f = this.y.redMul(l.redMul(c.redISub(l)).redISub(o.redMul(s)));
		f = f.redIAdd(f), f = f.redIAdd(f), f = f.redIAdd(f);
		var p = this.z.redAdd(o).redSqr().redISub(n).redISub(s);
		return this.curve.jpoint(d, f, p);
	}, l.prototype.mul = function(e, t) {
		return e = new r(e, t), this.curve._wnafMul(this, e);
	}, l.prototype.eq = function(e) {
		if (e.type === "affine") return this.eq(e.toJ());
		if (this === e) return !0;
		var t = this.z.redSqr(), n = e.z.redSqr();
		if (this.x.redMul(n).redISub(e.x.redMul(t)).cmpn(0) !== 0) return !1;
		var r = t.redMul(this.z), i = n.redMul(e.z);
		return this.y.redMul(i).redISub(e.y.redMul(r)).cmpn(0) === 0;
	}, l.prototype.eqXToP = function(e) {
		var t = this.z.redSqr(), n = e.toRed(this.curve.red).redMul(t);
		if (this.x.cmp(n) === 0) return !0;
		for (var r = e.clone(), i = this.curve.redN.redMul(t);;) {
			if (r.iadd(this.curve.n), r.cmp(this.curve.p) >= 0) return !1;
			if (n.redIAdd(i), this.x.cmp(n) === 0) return !0;
		}
	}, l.prototype.inspect = function() {
		return this.isInfinity() ? "<EC JPoint Infinity>" : "<EC JPoint x: " + this.x.toString(16, 2) + " y: " + this.y.toString(16, 2) + " z: " + this.z.toString(16, 2) + ">";
	}, l.prototype.isInfinity = function() {
		return this.z.cmpn(0) === 0;
	};
})), _s = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = hs(), i = ms(), a = fs();
	function o(e) {
		i.call(this, "mont", e), this.a = new n(e.a, 16).toRed(this.red), this.b = new n(e.b, 16).toRed(this.red), this.i4 = new n(4).toRed(this.red).redInvm(), this.two = new n(2).toRed(this.red), this.a24 = this.i4.redMul(this.a.redAdd(this.two));
	}
	r(o, i), t.exports = o, o.prototype.validate = function(e) {
		var t = e.normalize().x, n = t.redSqr(), r = n.redMul(t).redAdd(n.redMul(this.a)).redAdd(t);
		return r.redSqrt().redSqr().cmp(r) === 0;
	};
	function s(e, t, r) {
		i.BasePoint.call(this, e, "projective"), t === null && r === null ? (this.x = this.curve.one, this.z = this.curve.zero) : (this.x = new n(t, 16), this.z = new n(r, 16), this.x.red || (this.x = this.x.toRed(this.curve.red)), this.z.red || (this.z = this.z.toRed(this.curve.red)));
	}
	r(s, i.BasePoint), o.prototype.decodePoint = function(e, t) {
		return this.point(a.toArray(e, t), 1);
	}, o.prototype.point = function(e, t) {
		return new s(this, e, t);
	}, o.prototype.pointFromJSON = function(e) {
		return s.fromJSON(this, e);
	}, s.prototype.precompute = function() {}, s.prototype._encode = function() {
		return this.getX().toArray("be", this.curve.p.byteLength());
	}, s.fromJSON = function(e, t) {
		return new s(e, t[0], t[1] || e.one);
	}, s.prototype.inspect = function() {
		return this.isInfinity() ? "<EC Point Infinity>" : "<EC Point x: " + this.x.fromRed().toString(16, 2) + " z: " + this.z.fromRed().toString(16, 2) + ">";
	}, s.prototype.isInfinity = function() {
		return this.z.cmpn(0) === 0;
	}, s.prototype.dbl = function() {
		var e = this.x.redAdd(this.z).redSqr(), t = this.x.redSub(this.z).redSqr(), n = e.redSub(t), r = e.redMul(t), i = n.redMul(t.redAdd(this.curve.a24.redMul(n)));
		return this.curve.point(r, i);
	}, s.prototype.add = function() {
		throw Error("Not supported on Montgomery curve");
	}, s.prototype.diffAdd = function(e, t) {
		var n = this.x.redAdd(this.z), r = this.x.redSub(this.z), i = e.x.redAdd(e.z), a = e.x.redSub(e.z).redMul(n), o = i.redMul(r), s = t.z.redMul(a.redAdd(o).redSqr()), c = t.x.redMul(a.redISub(o).redSqr());
		return this.curve.point(s, c);
	}, s.prototype.mul = function(e) {
		for (var t = e.clone(), n = this, r = this.curve.point(null, null), i = this, a = []; t.cmpn(0) !== 0; t.iushrn(1)) a.push(t.andln(1));
		for (var o = a.length - 1; o >= 0; o--) a[o] === 0 ? (n = n.diffAdd(r, i), r = r.dbl()) : (r = n.diffAdd(r, i), n = n.dbl());
		return r;
	}, s.prototype.mulAdd = function() {
		throw Error("Not supported on Montgomery curve");
	}, s.prototype.jumlAdd = function() {
		throw Error("Not supported on Montgomery curve");
	}, s.prototype.eq = function(e) {
		return this.getX().cmp(e.getX()) === 0;
	}, s.prototype.normalize = function() {
		return this.x = this.x.redMul(this.z.redInvm()), this.z = this.curve.one, this;
	}, s.prototype.getX = function() {
		return this.normalize(), this.x.fromRed();
	};
})), vs = /* @__PURE__ */ s(((e, t) => {
	var n = fs(), r = ls(), i = hs(), a = ms(), o = n.assert;
	function s(e) {
		this.twisted = (e.a | 0) != 1, this.mOneA = this.twisted && (e.a | 0) == -1, this.extended = this.mOneA, a.call(this, "edwards", e), this.a = new r(e.a, 16).umod(this.red.m), this.a = this.a.toRed(this.red), this.c = new r(e.c, 16).toRed(this.red), this.c2 = this.c.redSqr(), this.d = new r(e.d, 16).toRed(this.red), this.dd = this.d.redAdd(this.d), o(!this.twisted || this.c.fromRed().cmpn(1) === 0), this.oneC = (e.c | 0) == 1;
	}
	i(s, a), t.exports = s, s.prototype._mulA = function(e) {
		return this.mOneA ? e.redNeg() : this.a.redMul(e);
	}, s.prototype._mulC = function(e) {
		return this.oneC ? e : this.c.redMul(e);
	}, s.prototype.jpoint = function(e, t, n, r) {
		return this.point(e, t, n, r);
	}, s.prototype.pointFromX = function(e, t) {
		e = new r(e, 16), e.red || (e = e.toRed(this.red));
		var n = e.redSqr(), i = this.c2.redSub(this.a.redMul(n)), a = this.one.redSub(this.c2.redMul(this.d).redMul(n)), o = i.redMul(a.redInvm()), s = o.redSqrt();
		if (s.redSqr().redSub(o).cmp(this.zero) !== 0) throw Error("invalid point");
		var c = s.fromRed().isOdd();
		return (t && !c || !t && c) && (s = s.redNeg()), this.point(e, s);
	}, s.prototype.pointFromY = function(e, t) {
		e = new r(e, 16), e.red || (e = e.toRed(this.red));
		var n = e.redSqr(), i = n.redSub(this.c2), a = n.redMul(this.d).redMul(this.c2).redSub(this.a), o = i.redMul(a.redInvm());
		if (o.cmp(this.zero) === 0) {
			if (t) throw Error("invalid point");
			return this.point(this.zero, e);
		}
		var s = o.redSqrt();
		if (s.redSqr().redSub(o).cmp(this.zero) !== 0) throw Error("invalid point");
		return s.fromRed().isOdd() !== t && (s = s.redNeg()), this.point(s, e);
	}, s.prototype.validate = function(e) {
		if (e.isInfinity()) return !0;
		e.normalize();
		var t = e.x.redSqr(), n = e.y.redSqr(), r = t.redMul(this.a).redAdd(n), i = this.c2.redMul(this.one.redAdd(this.d.redMul(t).redMul(n)));
		return r.cmp(i) === 0;
	};
	function c(e, t, n, i, o) {
		a.BasePoint.call(this, e, "projective"), t === null && n === null && i === null ? (this.x = this.curve.zero, this.y = this.curve.one, this.z = this.curve.one, this.t = this.curve.zero, this.zOne = !0) : (this.x = new r(t, 16), this.y = new r(n, 16), this.z = i ? new r(i, 16) : this.curve.one, this.t = o && new r(o, 16), this.x.red || (this.x = this.x.toRed(this.curve.red)), this.y.red || (this.y = this.y.toRed(this.curve.red)), this.z.red || (this.z = this.z.toRed(this.curve.red)), this.t && !this.t.red && (this.t = this.t.toRed(this.curve.red)), this.zOne = this.z === this.curve.one, this.curve.extended && !this.t && (this.t = this.x.redMul(this.y), this.zOne || (this.t = this.t.redMul(this.z.redInvm()))));
	}
	i(c, a.BasePoint), s.prototype.pointFromJSON = function(e) {
		return c.fromJSON(this, e);
	}, s.prototype.point = function(e, t, n, r) {
		return new c(this, e, t, n, r);
	}, c.fromJSON = function(e, t) {
		return new c(e, t[0], t[1], t[2]);
	}, c.prototype.inspect = function() {
		return this.isInfinity() ? "<EC Point Infinity>" : "<EC Point x: " + this.x.fromRed().toString(16, 2) + " y: " + this.y.fromRed().toString(16, 2) + " z: " + this.z.fromRed().toString(16, 2) + ">";
	}, c.prototype.isInfinity = function() {
		return this.x.cmpn(0) === 0 && (this.y.cmp(this.z) === 0 || this.zOne && this.y.cmp(this.curve.c) === 0);
	}, c.prototype._extDbl = function() {
		var e = this.x.redSqr(), t = this.y.redSqr(), n = this.z.redSqr();
		n = n.redIAdd(n);
		var r = this.curve._mulA(e), i = this.x.redAdd(this.y).redSqr().redISub(e).redISub(t), a = r.redAdd(t), o = a.redSub(n), s = r.redSub(t), c = i.redMul(o), l = a.redMul(s), u = i.redMul(s), d = o.redMul(a);
		return this.curve.point(c, l, d, u);
	}, c.prototype._projDbl = function() {
		var e = this.x.redAdd(this.y).redSqr(), t = this.x.redSqr(), n = this.y.redSqr(), r, i, a, o, s, c;
		if (this.curve.twisted) {
			o = this.curve._mulA(t);
			var l = o.redAdd(n);
			this.zOne ? (r = e.redSub(t).redSub(n).redMul(l.redSub(this.curve.two)), i = l.redMul(o.redSub(n)), a = l.redSqr().redSub(l).redSub(l)) : (s = this.z.redSqr(), c = l.redSub(s).redISub(s), r = e.redSub(t).redISub(n).redMul(c), i = l.redMul(o.redSub(n)), a = l.redMul(c));
		} else o = t.redAdd(n), s = this.curve._mulC(this.z).redSqr(), c = o.redSub(s).redSub(s), r = this.curve._mulC(e.redISub(o)).redMul(c), i = this.curve._mulC(o).redMul(t.redISub(n)), a = o.redMul(c);
		return this.curve.point(r, i, a);
	}, c.prototype.dbl = function() {
		return this.isInfinity() ? this : this.curve.extended ? this._extDbl() : this._projDbl();
	}, c.prototype._extAdd = function(e) {
		var t = this.y.redSub(this.x).redMul(e.y.redSub(e.x)), n = this.y.redAdd(this.x).redMul(e.y.redAdd(e.x)), r = this.t.redMul(this.curve.dd).redMul(e.t), i = this.z.redMul(e.z.redAdd(e.z)), a = n.redSub(t), o = i.redSub(r), s = i.redAdd(r), c = n.redAdd(t), l = a.redMul(o), u = s.redMul(c), d = a.redMul(c), f = o.redMul(s);
		return this.curve.point(l, u, f, d);
	}, c.prototype._projAdd = function(e) {
		var t = this.z.redMul(e.z), n = t.redSqr(), r = this.x.redMul(e.x), i = this.y.redMul(e.y), a = this.curve.d.redMul(r).redMul(i), o = n.redSub(a), s = n.redAdd(a), c = this.x.redAdd(this.y).redMul(e.x.redAdd(e.y)).redISub(r).redISub(i), l = t.redMul(o).redMul(c), u, d;
		return this.curve.twisted ? (u = t.redMul(s).redMul(i.redSub(this.curve._mulA(r))), d = o.redMul(s)) : (u = t.redMul(s).redMul(i.redSub(r)), d = this.curve._mulC(o).redMul(s)), this.curve.point(l, u, d);
	}, c.prototype.add = function(e) {
		return this.isInfinity() ? e : e.isInfinity() ? this : this.curve.extended ? this._extAdd(e) : this._projAdd(e);
	}, c.prototype.mul = function(e) {
		return this._hasDoubles(e) ? this.curve._fixedNafMul(this, e) : this.curve._wnafMul(this, e);
	}, c.prototype.mulAdd = function(e, t, n) {
		return this.curve._wnafMulAdd(1, [this, t], [e, n], 2, !1);
	}, c.prototype.jmulAdd = function(e, t, n) {
		return this.curve._wnafMulAdd(1, [this, t], [e, n], 2, !0);
	}, c.prototype.normalize = function() {
		if (this.zOne) return this;
		var e = this.z.redInvm();
		return this.x = this.x.redMul(e), this.y = this.y.redMul(e), this.t &&= this.t.redMul(e), this.z = this.curve.one, this.zOne = !0, this;
	}, c.prototype.neg = function() {
		return this.curve.point(this.x.redNeg(), this.y, this.z, this.t && this.t.redNeg());
	}, c.prototype.getX = function() {
		return this.normalize(), this.x.fromRed();
	}, c.prototype.getY = function() {
		return this.normalize(), this.y.fromRed();
	}, c.prototype.eq = function(e) {
		return this === e || this.getX().cmp(e.getX()) === 0 && this.getY().cmp(e.getY()) === 0;
	}, c.prototype.eqXToP = function(e) {
		var t = e.toRed(this.curve.red).redMul(this.z);
		if (this.x.cmp(t) === 0) return !0;
		for (var n = e.clone(), r = this.curve.redN.redMul(this.z);;) {
			if (n.iadd(this.curve.n), n.cmp(this.curve.p) >= 0) return !1;
			if (t.redIAdd(r), this.x.cmp(t) === 0) return !0;
		}
	}, c.prototype.toP = c.prototype.normalize, c.prototype.mixedAdd = c.prototype.add;
})), ys = /* @__PURE__ */ s(((e) => {
	var t = e;
	t.base = ms(), t.short = gs(), t.mont = _s(), t.edwards = vs();
})), bs = /* @__PURE__ */ s(((e) => {
	var t = us();
	e.inherits = hs();
	function n(e, t) {
		return (e.charCodeAt(t) & 64512) != 55296 || t < 0 || t + 1 >= e.length ? !1 : (e.charCodeAt(t + 1) & 64512) == 56320;
	}
	function r(e, t) {
		if (Array.isArray(e)) return e.slice();
		if (!e) return [];
		var r = [];
		if (typeof e == "string") {
			if (!t) for (var i = 0, a = 0; a < e.length; a++) {
				var o = e.charCodeAt(a);
				o < 128 ? r[i++] = o : o < 2048 ? (r[i++] = o >> 6 | 192, r[i++] = o & 63 | 128) : n(e, a) ? (o = 65536 + ((o & 1023) << 10) + (e.charCodeAt(++a) & 1023), r[i++] = o >> 18 | 240, r[i++] = o >> 12 & 63 | 128, r[i++] = o >> 6 & 63 | 128, r[i++] = o & 63 | 128) : (r[i++] = o >> 12 | 224, r[i++] = o >> 6 & 63 | 128, r[i++] = o & 63 | 128);
			}
			else if (t === "hex") for (e = e.replace(/[^a-z0-9]+/gi, ""), e.length % 2 != 0 && (e = "0" + e), a = 0; a < e.length; a += 2) r.push(parseInt(e[a] + e[a + 1], 16));
		} else for (a = 0; a < e.length; a++) r[a] = e[a] | 0;
		return r;
	}
	e.toArray = r;
	function i(e) {
		for (var t = "", n = 0; n < e.length; n++) t += s(e[n].toString(16));
		return t;
	}
	e.toHex = i;
	function a(e) {
		return (e >>> 24 | e >>> 8 & 65280 | e << 8 & 16711680 | (e & 255) << 24) >>> 0;
	}
	e.htonl = a;
	function o(e, t) {
		for (var n = "", r = 0; r < e.length; r++) {
			var i = e[r];
			t === "little" && (i = a(i)), n += c(i.toString(16));
		}
		return n;
	}
	e.toHex32 = o;
	function s(e) {
		return e.length === 1 ? "0" + e : e;
	}
	e.zero2 = s;
	function c(e) {
		return e.length === 7 ? "0" + e : e.length === 6 ? "00" + e : e.length === 5 ? "000" + e : e.length === 4 ? "0000" + e : e.length === 3 ? "00000" + e : e.length === 2 ? "000000" + e : e.length === 1 ? "0000000" + e : e;
	}
	e.zero8 = c;
	function l(e, n, r, i) {
		var a = r - n;
		t(a % 4 == 0);
		for (var o = Array(a / 4), s = 0, c = n; s < o.length; s++, c += 4) o[s] = (i === "big" ? e[c] << 24 | e[c + 1] << 16 | e[c + 2] << 8 | e[c + 3] : e[c + 3] << 24 | e[c + 2] << 16 | e[c + 1] << 8 | e[c]) >>> 0;
		return o;
	}
	e.join32 = l;
	function u(e, t) {
		for (var n = Array(e.length * 4), r = 0, i = 0; r < e.length; r++, i += 4) {
			var a = e[r];
			t === "big" ? (n[i] = a >>> 24, n[i + 1] = a >>> 16 & 255, n[i + 2] = a >>> 8 & 255, n[i + 3] = a & 255) : (n[i + 3] = a >>> 24, n[i + 2] = a >>> 16 & 255, n[i + 1] = a >>> 8 & 255, n[i] = a & 255);
		}
		return n;
	}
	e.split32 = u;
	function d(e, t) {
		return e >>> t | e << 32 - t;
	}
	e.rotr32 = d;
	function f(e, t) {
		return e << t | e >>> 32 - t;
	}
	e.rotl32 = f;
	function p(e, t) {
		return e + t >>> 0;
	}
	e.sum32 = p;
	function m(e, t, n) {
		return e + t + n >>> 0;
	}
	e.sum32_3 = m;
	function h(e, t, n, r) {
		return e + t + n + r >>> 0;
	}
	e.sum32_4 = h;
	function g(e, t, n, r, i) {
		return e + t + n + r + i >>> 0;
	}
	e.sum32_5 = g;
	function _(e, t, n, r) {
		var i = e[t], a = r + e[t + 1] >>> 0;
		e[t] = (a < r ? 1 : 0) + n + i >>> 0, e[t + 1] = a;
	}
	e.sum64 = _;
	function v(e, t, n, r) {
		return (t + r >>> 0 < t ? 1 : 0) + e + n >>> 0;
	}
	e.sum64_hi = v;
	function y(e, t, n, r) {
		return t + r >>> 0;
	}
	e.sum64_lo = y;
	function b(e, t, n, r, i, a, o, s) {
		var c = 0, l = t;
		return l = l + r >>> 0, c += l < t ? 1 : 0, l = l + a >>> 0, c += l < a ? 1 : 0, l = l + s >>> 0, c += l < s ? 1 : 0, e + n + i + o + c >>> 0;
	}
	e.sum64_4_hi = b;
	function x(e, t, n, r, i, a, o, s) {
		return t + r + a + s >>> 0;
	}
	e.sum64_4_lo = x;
	function S(e, t, n, r, i, a, o, s, c, l) {
		var u = 0, d = t;
		return d = d + r >>> 0, u += d < t ? 1 : 0, d = d + a >>> 0, u += d < a ? 1 : 0, d = d + s >>> 0, u += d < s ? 1 : 0, d = d + l >>> 0, u += d < l ? 1 : 0, e + n + i + o + c + u >>> 0;
	}
	e.sum64_5_hi = S;
	function C(e, t, n, r, i, a, o, s, c, l) {
		return t + r + a + s + l >>> 0;
	}
	e.sum64_5_lo = C;
	function w(e, t, n) {
		return (t << 32 - n | e >>> n) >>> 0;
	}
	e.rotr64_hi = w;
	function T(e, t, n) {
		return (e << 32 - n | t >>> n) >>> 0;
	}
	e.rotr64_lo = T;
	function E(e, t, n) {
		return e >>> n;
	}
	e.shr64_hi = E;
	function D(e, t, n) {
		return (e << 32 - n | t >>> n) >>> 0;
	}
	e.shr64_lo = D;
})), xs = /* @__PURE__ */ s(((e) => {
	var t = bs(), n = us();
	function r() {
		this.pending = null, this.pendingTotal = 0, this.blockSize = this.constructor.blockSize, this.outSize = this.constructor.outSize, this.hmacStrength = this.constructor.hmacStrength, this.padLength = this.constructor.padLength / 8, this.endian = "big", this._delta8 = this.blockSize / 8, this._delta32 = this.blockSize / 32;
	}
	e.BlockHash = r, r.prototype.update = function(e, n) {
		if (e = t.toArray(e, n), this.pending ? this.pending = this.pending.concat(e) : this.pending = e, this.pendingTotal += e.length, this.pending.length >= this._delta8) {
			e = this.pending;
			var r = e.length % this._delta8;
			this.pending = e.slice(e.length - r, e.length), this.pending.length === 0 && (this.pending = null), e = t.join32(e, 0, e.length - r, this.endian);
			for (var i = 0; i < e.length; i += this._delta32) this._update(e, i, i + this._delta32);
		}
		return this;
	}, r.prototype.digest = function(e) {
		return this.update(this._pad()), n(this.pending === null), this._digest(e);
	}, r.prototype._pad = function() {
		var e = this.pendingTotal, t = this._delta8, n = t - (e + this.padLength) % t, r = Array(n + this.padLength);
		r[0] = 128;
		for (var i = 1; i < n; i++) r[i] = 0;
		if (e <<= 3, this.endian === "big") {
			for (var a = 8; a < this.padLength; a++) r[i++] = 0;
			r[i++] = 0, r[i++] = 0, r[i++] = 0, r[i++] = 0, r[i++] = e >>> 24 & 255, r[i++] = e >>> 16 & 255, r[i++] = e >>> 8 & 255, r[i++] = e & 255;
		} else for (r[i++] = e & 255, r[i++] = e >>> 8 & 255, r[i++] = e >>> 16 & 255, r[i++] = e >>> 24 & 255, r[i++] = 0, r[i++] = 0, r[i++] = 0, r[i++] = 0, a = 8; a < this.padLength; a++) r[i++] = 0;
		return r;
	};
})), Ss = /* @__PURE__ */ s(((e) => {
	var t = bs().rotr32;
	function n(e, t, n, o) {
		if (e === 0) return r(t, n, o);
		if (e === 1 || e === 3) return a(t, n, o);
		if (e === 2) return i(t, n, o);
	}
	e.ft_1 = n;
	function r(e, t, n) {
		return e & t ^ ~e & n;
	}
	e.ch32 = r;
	function i(e, t, n) {
		return e & t ^ e & n ^ t & n;
	}
	e.maj32 = i;
	function a(e, t, n) {
		return e ^ t ^ n;
	}
	e.p32 = a;
	function o(e) {
		return t(e, 2) ^ t(e, 13) ^ t(e, 22);
	}
	e.s0_256 = o;
	function s(e) {
		return t(e, 6) ^ t(e, 11) ^ t(e, 25);
	}
	e.s1_256 = s;
	function c(e) {
		return t(e, 7) ^ t(e, 18) ^ e >>> 3;
	}
	e.g0_256 = c;
	function l(e) {
		return t(e, 17) ^ t(e, 19) ^ e >>> 10;
	}
	e.g1_256 = l;
})), Cs = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = xs(), i = Ss(), a = n.rotl32, o = n.sum32, s = n.sum32_5, c = i.ft_1, l = r.BlockHash, u = [
		1518500249,
		1859775393,
		2400959708,
		3395469782
	];
	function d() {
		if (!(this instanceof d)) return new d();
		l.call(this), this.h = [
			1732584193,
			4023233417,
			2562383102,
			271733878,
			3285377520
		], this.W = Array(80);
	}
	n.inherits(d, l), t.exports = d, d.blockSize = 512, d.outSize = 160, d.hmacStrength = 80, d.padLength = 64, d.prototype._update = function(e, t) {
		for (var n = this.W, r = 0; r < 16; r++) n[r] = e[t + r];
		for (; r < n.length; r++) n[r] = a(n[r - 3] ^ n[r - 8] ^ n[r - 14] ^ n[r - 16], 1);
		var i = this.h[0], l = this.h[1], d = this.h[2], f = this.h[3], p = this.h[4];
		for (r = 0; r < n.length; r++) {
			var m = ~~(r / 20), h = s(a(i, 5), c(m, l, d, f), p, n[r], u[m]);
			p = f, f = d, d = a(l, 30), l = i, i = h;
		}
		this.h[0] = o(this.h[0], i), this.h[1] = o(this.h[1], l), this.h[2] = o(this.h[2], d), this.h[3] = o(this.h[3], f), this.h[4] = o(this.h[4], p);
	}, d.prototype._digest = function(e) {
		return e === "hex" ? n.toHex32(this.h, "big") : n.split32(this.h, "big");
	};
})), ws = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = xs(), i = Ss(), a = us(), o = n.sum32, s = n.sum32_4, c = n.sum32_5, l = i.ch32, u = i.maj32, d = i.s0_256, f = i.s1_256, p = i.g0_256, m = i.g1_256, h = r.BlockHash, g = [
		1116352408,
		1899447441,
		3049323471,
		3921009573,
		961987163,
		1508970993,
		2453635748,
		2870763221,
		3624381080,
		310598401,
		607225278,
		1426881987,
		1925078388,
		2162078206,
		2614888103,
		3248222580,
		3835390401,
		4022224774,
		264347078,
		604807628,
		770255983,
		1249150122,
		1555081692,
		1996064986,
		2554220882,
		2821834349,
		2952996808,
		3210313671,
		3336571891,
		3584528711,
		113926993,
		338241895,
		666307205,
		773529912,
		1294757372,
		1396182291,
		1695183700,
		1986661051,
		2177026350,
		2456956037,
		2730485921,
		2820302411,
		3259730800,
		3345764771,
		3516065817,
		3600352804,
		4094571909,
		275423344,
		430227734,
		506948616,
		659060556,
		883997877,
		958139571,
		1322822218,
		1537002063,
		1747873779,
		1955562222,
		2024104815,
		2227730452,
		2361852424,
		2428436474,
		2756734187,
		3204031479,
		3329325298
	];
	function _() {
		if (!(this instanceof _)) return new _();
		h.call(this), this.h = [
			1779033703,
			3144134277,
			1013904242,
			2773480762,
			1359893119,
			2600822924,
			528734635,
			1541459225
		], this.k = g, this.W = Array(64);
	}
	n.inherits(_, h), t.exports = _, _.blockSize = 512, _.outSize = 256, _.hmacStrength = 192, _.padLength = 64, _.prototype._update = function(e, t) {
		for (var n = this.W, r = 0; r < 16; r++) n[r] = e[t + r];
		for (; r < n.length; r++) n[r] = s(m(n[r - 2]), n[r - 7], p(n[r - 15]), n[r - 16]);
		var i = this.h[0], h = this.h[1], g = this.h[2], _ = this.h[3], v = this.h[4], y = this.h[5], b = this.h[6], x = this.h[7];
		for (a(this.k.length === n.length), r = 0; r < n.length; r++) {
			var S = c(x, f(v), l(v, y, b), this.k[r], n[r]), C = o(d(i), u(i, h, g));
			x = b, b = y, y = v, v = o(_, S), _ = g, g = h, h = i, i = o(S, C);
		}
		this.h[0] = o(this.h[0], i), this.h[1] = o(this.h[1], h), this.h[2] = o(this.h[2], g), this.h[3] = o(this.h[3], _), this.h[4] = o(this.h[4], v), this.h[5] = o(this.h[5], y), this.h[6] = o(this.h[6], b), this.h[7] = o(this.h[7], x);
	}, _.prototype._digest = function(e) {
		return e === "hex" ? n.toHex32(this.h, "big") : n.split32(this.h, "big");
	};
})), Ts = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = ws();
	function i() {
		if (!(this instanceof i)) return new i();
		r.call(this), this.h = [
			3238371032,
			914150663,
			812702999,
			4144912697,
			4290775857,
			1750603025,
			1694076839,
			3204075428
		];
	}
	n.inherits(i, r), t.exports = i, i.blockSize = 512, i.outSize = 224, i.hmacStrength = 192, i.padLength = 64, i.prototype._digest = function(e) {
		return e === "hex" ? n.toHex32(this.h.slice(0, 7), "big") : n.split32(this.h.slice(0, 7), "big");
	};
})), Es = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = xs(), i = us(), a = n.rotr64_hi, o = n.rotr64_lo, s = n.shr64_hi, c = n.shr64_lo, l = n.sum64, u = n.sum64_hi, d = n.sum64_lo, f = n.sum64_4_hi, p = n.sum64_4_lo, m = n.sum64_5_hi, h = n.sum64_5_lo, g = r.BlockHash, _ = [
		1116352408,
		3609767458,
		1899447441,
		602891725,
		3049323471,
		3964484399,
		3921009573,
		2173295548,
		961987163,
		4081628472,
		1508970993,
		3053834265,
		2453635748,
		2937671579,
		2870763221,
		3664609560,
		3624381080,
		2734883394,
		310598401,
		1164996542,
		607225278,
		1323610764,
		1426881987,
		3590304994,
		1925078388,
		4068182383,
		2162078206,
		991336113,
		2614888103,
		633803317,
		3248222580,
		3479774868,
		3835390401,
		2666613458,
		4022224774,
		944711139,
		264347078,
		2341262773,
		604807628,
		2007800933,
		770255983,
		1495990901,
		1249150122,
		1856431235,
		1555081692,
		3175218132,
		1996064986,
		2198950837,
		2554220882,
		3999719339,
		2821834349,
		766784016,
		2952996808,
		2566594879,
		3210313671,
		3203337956,
		3336571891,
		1034457026,
		3584528711,
		2466948901,
		113926993,
		3758326383,
		338241895,
		168717936,
		666307205,
		1188179964,
		773529912,
		1546045734,
		1294757372,
		1522805485,
		1396182291,
		2643833823,
		1695183700,
		2343527390,
		1986661051,
		1014477480,
		2177026350,
		1206759142,
		2456956037,
		344077627,
		2730485921,
		1290863460,
		2820302411,
		3158454273,
		3259730800,
		3505952657,
		3345764771,
		106217008,
		3516065817,
		3606008344,
		3600352804,
		1432725776,
		4094571909,
		1467031594,
		275423344,
		851169720,
		430227734,
		3100823752,
		506948616,
		1363258195,
		659060556,
		3750685593,
		883997877,
		3785050280,
		958139571,
		3318307427,
		1322822218,
		3812723403,
		1537002063,
		2003034995,
		1747873779,
		3602036899,
		1955562222,
		1575990012,
		2024104815,
		1125592928,
		2227730452,
		2716904306,
		2361852424,
		442776044,
		2428436474,
		593698344,
		2756734187,
		3733110249,
		3204031479,
		2999351573,
		3329325298,
		3815920427,
		3391569614,
		3928383900,
		3515267271,
		566280711,
		3940187606,
		3454069534,
		4118630271,
		4000239992,
		116418474,
		1914138554,
		174292421,
		2731055270,
		289380356,
		3203993006,
		460393269,
		320620315,
		685471733,
		587496836,
		852142971,
		1086792851,
		1017036298,
		365543100,
		1126000580,
		2618297676,
		1288033470,
		3409855158,
		1501505948,
		4234509866,
		1607167915,
		987167468,
		1816402316,
		1246189591
	];
	function v() {
		if (!(this instanceof v)) return new v();
		g.call(this), this.h = [
			1779033703,
			4089235720,
			3144134277,
			2227873595,
			1013904242,
			4271175723,
			2773480762,
			1595750129,
			1359893119,
			2917565137,
			2600822924,
			725511199,
			528734635,
			4215389547,
			1541459225,
			327033209
		], this.k = _, this.W = Array(160);
	}
	n.inherits(v, g), t.exports = v, v.blockSize = 1024, v.outSize = 512, v.hmacStrength = 192, v.padLength = 128, v.prototype._prepareBlock = function(e, t) {
		for (var n = this.W, r = 0; r < 32; r++) n[r] = e[t + r];
		for (; r < n.length; r += 2) {
			var i = O(n[r - 4], n[r - 3]), a = k(n[r - 4], n[r - 3]), o = n[r - 14], s = n[r - 13], c = D(n[r - 30], n[r - 29]), l = ee(n[r - 30], n[r - 29]), u = n[r - 32], d = n[r - 31];
			n[r] = f(i, a, o, s, c, l, u, d), n[r + 1] = p(i, a, o, s, c, l, u, d);
		}
	}, v.prototype._update = function(e, t) {
		this._prepareBlock(e, t);
		var n = this.W, r = this.h[0], a = this.h[1], o = this.h[2], s = this.h[3], c = this.h[4], f = this.h[5], p = this.h[6], g = this.h[7], _ = this.h[8], v = this.h[9], D = this.h[10], ee = this.h[11], O = this.h[12], k = this.h[13], te = this.h[14], A = this.h[15];
		i(this.k.length === n.length);
		for (var j = 0; j < n.length; j += 2) {
			var ne = te, M = A, N = T(_, v), re = E(_, v), ie = y(_, v, D, ee, O, k), P = b(_, v, D, ee, O, k), ae = this.k[j], F = this.k[j + 1], oe = n[j], se = n[j + 1], I = m(ne, M, N, re, ie, P, ae, F, oe, se), L = h(ne, M, N, re, ie, P, ae, F, oe, se);
			ne = C(r, a), M = w(r, a), N = x(r, a, o, s, c, f), re = S(r, a, o, s, c, f);
			var ce = u(ne, M, N, re), R = d(ne, M, N, re);
			te = O, A = k, O = D, k = ee, D = _, ee = v, _ = u(p, g, I, L), v = d(g, g, I, L), p = c, g = f, c = o, f = s, o = r, s = a, r = u(I, L, ce, R), a = d(I, L, ce, R);
		}
		l(this.h, 0, r, a), l(this.h, 2, o, s), l(this.h, 4, c, f), l(this.h, 6, p, g), l(this.h, 8, _, v), l(this.h, 10, D, ee), l(this.h, 12, O, k), l(this.h, 14, te, A);
	}, v.prototype._digest = function(e) {
		return e === "hex" ? n.toHex32(this.h, "big") : n.split32(this.h, "big");
	};
	function y(e, t, n, r, i) {
		var a = e & n ^ ~e & i;
		return a < 0 && (a += 4294967296), a;
	}
	function b(e, t, n, r, i, a) {
		var o = t & r ^ ~t & a;
		return o < 0 && (o += 4294967296), o;
	}
	function x(e, t, n, r, i) {
		var a = e & n ^ e & i ^ n & i;
		return a < 0 && (a += 4294967296), a;
	}
	function S(e, t, n, r, i, a) {
		var o = t & r ^ t & a ^ r & a;
		return o < 0 && (o += 4294967296), o;
	}
	function C(e, t) {
		var n = a(e, t, 28), r = a(t, e, 2), i = a(t, e, 7), o = n ^ r ^ i;
		return o < 0 && (o += 4294967296), o;
	}
	function w(e, t) {
		var n = o(e, t, 28), r = o(t, e, 2), i = o(t, e, 7), a = n ^ r ^ i;
		return a < 0 && (a += 4294967296), a;
	}
	function T(e, t) {
		var n = a(e, t, 14), r = a(e, t, 18), i = a(t, e, 9), o = n ^ r ^ i;
		return o < 0 && (o += 4294967296), o;
	}
	function E(e, t) {
		var n = o(e, t, 14), r = o(e, t, 18), i = o(t, e, 9), a = n ^ r ^ i;
		return a < 0 && (a += 4294967296), a;
	}
	function D(e, t) {
		var n = a(e, t, 1), r = a(e, t, 8), i = s(e, t, 7), o = n ^ r ^ i;
		return o < 0 && (o += 4294967296), o;
	}
	function ee(e, t) {
		var n = o(e, t, 1), r = o(e, t, 8), i = c(e, t, 7), a = n ^ r ^ i;
		return a < 0 && (a += 4294967296), a;
	}
	function O(e, t) {
		var n = a(e, t, 19), r = a(t, e, 29), i = s(e, t, 6), o = n ^ r ^ i;
		return o < 0 && (o += 4294967296), o;
	}
	function k(e, t) {
		var n = o(e, t, 19), r = o(t, e, 29), i = c(e, t, 6), a = n ^ r ^ i;
		return a < 0 && (a += 4294967296), a;
	}
})), Ds = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = Es();
	function i() {
		if (!(this instanceof i)) return new i();
		r.call(this), this.h = [
			3418070365,
			3238371032,
			1654270250,
			914150663,
			2438529370,
			812702999,
			355462360,
			4144912697,
			1731405415,
			4290775857,
			2394180231,
			1750603025,
			3675008525,
			1694076839,
			1203062813,
			3204075428
		];
	}
	n.inherits(i, r), t.exports = i, i.blockSize = 1024, i.outSize = 384, i.hmacStrength = 192, i.padLength = 128, i.prototype._digest = function(e) {
		return e === "hex" ? n.toHex32(this.h.slice(0, 12), "big") : n.split32(this.h.slice(0, 12), "big");
	};
})), Os = /* @__PURE__ */ s(((e) => {
	e.sha1 = Cs(), e.sha224 = Ts(), e.sha256 = ws(), e.sha384 = Ds(), e.sha512 = Es();
})), ks = /* @__PURE__ */ s(((e) => {
	var t = bs(), n = xs(), r = t.rotl32, i = t.sum32, a = t.sum32_3, o = t.sum32_4, s = n.BlockHash;
	function c() {
		if (!(this instanceof c)) return new c();
		s.call(this), this.h = [
			1732584193,
			4023233417,
			2562383102,
			271733878,
			3285377520
		], this.endian = "little";
	}
	t.inherits(c, s), e.ripemd160 = c, c.blockSize = 512, c.outSize = 160, c.hmacStrength = 192, c.padLength = 64, c.prototype._update = function(e, t) {
		for (var n = this.h[0], s = this.h[1], c = this.h[2], g = this.h[3], _ = this.h[4], v = n, y = s, b = c, x = g, S = _, C = 0; C < 80; C++) {
			var w = i(r(o(n, l(C, s, c, g), e[f[C] + t], u(C)), m[C]), _);
			n = _, _ = g, g = r(c, 10), c = s, s = w, w = i(r(o(v, l(79 - C, y, b, x), e[p[C] + t], d(C)), h[C]), S), v = S, S = x, x = r(b, 10), b = y, y = w;
		}
		w = a(this.h[1], c, x), this.h[1] = a(this.h[2], g, S), this.h[2] = a(this.h[3], _, v), this.h[3] = a(this.h[4], n, y), this.h[4] = a(this.h[0], s, b), this.h[0] = w;
	}, c.prototype._digest = function(e) {
		return e === "hex" ? t.toHex32(this.h, "little") : t.split32(this.h, "little");
	};
	function l(e, t, n, r) {
		return e <= 15 ? t ^ n ^ r : e <= 31 ? t & n | ~t & r : e <= 47 ? (t | ~n) ^ r : e <= 63 ? t & r | n & ~r : t ^ (n | ~r);
	}
	function u(e) {
		return e <= 15 ? 0 : e <= 31 ? 1518500249 : e <= 47 ? 1859775393 : e <= 63 ? 2400959708 : 2840853838;
	}
	function d(e) {
		return e <= 15 ? 1352829926 : e <= 31 ? 1548603684 : e <= 47 ? 1836072691 : e <= 63 ? 2053994217 : 0;
	}
	var f = [
		0,
		1,
		2,
		3,
		4,
		5,
		6,
		7,
		8,
		9,
		10,
		11,
		12,
		13,
		14,
		15,
		7,
		4,
		13,
		1,
		10,
		6,
		15,
		3,
		12,
		0,
		9,
		5,
		2,
		14,
		11,
		8,
		3,
		10,
		14,
		4,
		9,
		15,
		8,
		1,
		2,
		7,
		0,
		6,
		13,
		11,
		5,
		12,
		1,
		9,
		11,
		10,
		0,
		8,
		12,
		4,
		13,
		3,
		7,
		15,
		14,
		5,
		6,
		2,
		4,
		0,
		5,
		9,
		7,
		12,
		2,
		10,
		14,
		1,
		3,
		8,
		11,
		6,
		15,
		13
	], p = [
		5,
		14,
		7,
		0,
		9,
		2,
		11,
		4,
		13,
		6,
		15,
		8,
		1,
		10,
		3,
		12,
		6,
		11,
		3,
		7,
		0,
		13,
		5,
		10,
		14,
		15,
		8,
		12,
		4,
		9,
		1,
		2,
		15,
		5,
		1,
		3,
		7,
		14,
		6,
		9,
		11,
		8,
		12,
		2,
		10,
		0,
		4,
		13,
		8,
		6,
		4,
		1,
		3,
		11,
		15,
		0,
		5,
		12,
		2,
		13,
		9,
		7,
		10,
		14,
		12,
		15,
		10,
		4,
		1,
		5,
		8,
		7,
		6,
		2,
		13,
		14,
		0,
		3,
		9,
		11
	], m = [
		11,
		14,
		15,
		12,
		5,
		8,
		7,
		9,
		11,
		13,
		14,
		15,
		6,
		7,
		9,
		8,
		7,
		6,
		8,
		13,
		11,
		9,
		7,
		15,
		7,
		12,
		15,
		9,
		11,
		7,
		13,
		12,
		11,
		13,
		6,
		7,
		14,
		9,
		13,
		15,
		14,
		8,
		13,
		6,
		5,
		12,
		7,
		5,
		11,
		12,
		14,
		15,
		14,
		15,
		9,
		8,
		9,
		14,
		5,
		6,
		8,
		6,
		5,
		12,
		9,
		15,
		5,
		11,
		6,
		8,
		13,
		12,
		5,
		12,
		13,
		14,
		11,
		8,
		5,
		6
	], h = [
		8,
		9,
		9,
		11,
		13,
		15,
		15,
		5,
		7,
		7,
		8,
		11,
		14,
		14,
		12,
		6,
		9,
		13,
		15,
		7,
		12,
		8,
		9,
		11,
		7,
		7,
		12,
		7,
		6,
		15,
		13,
		11,
		9,
		7,
		15,
		11,
		8,
		6,
		6,
		14,
		12,
		13,
		5,
		14,
		13,
		13,
		7,
		5,
		15,
		5,
		8,
		11,
		14,
		14,
		6,
		14,
		6,
		9,
		12,
		9,
		12,
		5,
		15,
		8,
		8,
		5,
		12,
		9,
		12,
		5,
		14,
		6,
		8,
		13,
		6,
		5,
		15,
		13,
		11,
		11
	];
})), As = /* @__PURE__ */ s(((e, t) => {
	var n = bs(), r = us();
	function i(e, t, r) {
		if (!(this instanceof i)) return new i(e, t, r);
		this.Hash = e, this.blockSize = e.blockSize / 8, this.outSize = e.outSize / 8, this.inner = null, this.outer = null, this._init(n.toArray(t, r));
	}
	t.exports = i, i.prototype._init = function(e) {
		e.length > this.blockSize && (e = new this.Hash().update(e).digest()), r(e.length <= this.blockSize);
		for (var t = e.length; t < this.blockSize; t++) e.push(0);
		for (t = 0; t < e.length; t++) e[t] ^= 54;
		for (this.inner = new this.Hash().update(e), t = 0; t < e.length; t++) e[t] ^= 106;
		this.outer = new this.Hash().update(e);
	}, i.prototype.update = function(e, t) {
		return this.inner.update(e, t), this;
	}, i.prototype.digest = function(e) {
		return this.outer.update(this.inner.digest()), this.outer.digest(e);
	};
})), js = /* @__PURE__ */ s(((e) => {
	var t = e;
	t.utils = bs(), t.common = xs(), t.sha = Os(), t.ripemd = ks(), t.hmac = As(), t.sha1 = t.sha.sha1, t.sha256 = t.sha.sha256, t.sha224 = t.sha.sha224, t.sha384 = t.sha.sha384, t.sha512 = t.sha.sha512, t.ripemd160 = t.ripemd.ripemd160;
})), Ms = /* @__PURE__ */ s(((e, t) => {
	t.exports = {
		doubles: {
			step: 4,
			points: [
				["e60fce93b59e9ec53011aabc21c23e97b2a31369b87a5ae9c44ee89e2a6dec0a", "f7e3507399e595929db99f34f57937101296891e44d23f0be1f32cce69616821"],
				["8282263212c609d9ea2a6e3e172de238d8c39cabd5ac1ca10646e23fd5f51508", "11f8a8098557dfe45e8256e830b60ace62d613ac2f7b17bed31b6eaff6e26caf"],
				["175e159f728b865a72f99cc6c6fc846de0b93833fd2222ed73fce5b551e5b739", "d3506e0d9e3c79eba4ef97a51ff71f5eacb5955add24345c6efa6ffee9fed695"],
				["363d90d447b00c9c99ceac05b6262ee053441c7e55552ffe526bad8f83ff4640", "4e273adfc732221953b445397f3363145b9a89008199ecb62003c7f3bee9de9"],
				["8b4b5f165df3c2be8c6244b5b745638843e4a781a15bcd1b69f79a55dffdf80c", "4aad0a6f68d308b4b3fbd7813ab0da04f9e336546162ee56b3eff0c65fd4fd36"],
				["723cbaa6e5db996d6bf771c00bd548c7b700dbffa6c0e77bcb6115925232fcda", "96e867b5595cc498a921137488824d6e2660a0653779494801dc069d9eb39f5f"],
				["eebfa4d493bebf98ba5feec812c2d3b50947961237a919839a533eca0e7dd7fa", "5d9a8ca3970ef0f269ee7edaf178089d9ae4cdc3a711f712ddfd4fdae1de8999"],
				["100f44da696e71672791d0a09b7bde459f1215a29b3c03bfefd7835b39a48db0", "cdd9e13192a00b772ec8f3300c090666b7ff4a18ff5195ac0fbd5cd62bc65a09"],
				["e1031be262c7ed1b1dc9227a4a04c017a77f8d4464f3b3852c8acde6e534fd2d", "9d7061928940405e6bb6a4176597535af292dd419e1ced79a44f18f29456a00d"],
				["feea6cae46d55b530ac2839f143bd7ec5cf8b266a41d6af52d5e688d9094696d", "e57c6b6c97dce1bab06e4e12bf3ecd5c981c8957cc41442d3155debf18090088"],
				["da67a91d91049cdcb367be4be6ffca3cfeed657d808583de33fa978bc1ec6cb1", "9bacaa35481642bc41f463f7ec9780e5dec7adc508f740a17e9ea8e27a68be1d"],
				["53904faa0b334cdda6e000935ef22151ec08d0f7bb11069f57545ccc1a37b7c0", "5bc087d0bc80106d88c9eccac20d3c1c13999981e14434699dcb096b022771c8"],
				["8e7bcd0bd35983a7719cca7764ca906779b53a043a9b8bcaeff959f43ad86047", "10b7770b2a3da4b3940310420ca9514579e88e2e47fd68b3ea10047e8460372a"],
				["385eed34c1cdff21e6d0818689b81bde71a7f4f18397e6690a841e1599c43862", "283bebc3e8ea23f56701de19e9ebf4576b304eec2086dc8cc0458fe5542e5453"],
				["6f9d9b803ecf191637c73a4413dfa180fddf84a5947fbc9c606ed86c3fac3a7", "7c80c68e603059ba69b8e2a30e45c4d47ea4dd2f5c281002d86890603a842160"],
				["3322d401243c4e2582a2147c104d6ecbf774d163db0f5e5313b7e0e742d0e6bd", "56e70797e9664ef5bfb019bc4ddaf9b72805f63ea2873af624f3a2e96c28b2a0"],
				["85672c7d2de0b7da2bd1770d89665868741b3f9af7643397721d74d28134ab83", "7c481b9b5b43b2eb6374049bfa62c2e5e77f17fcc5298f44c8e3094f790313a6"],
				["948bf809b1988a46b06c9f1919413b10f9226c60f668832ffd959af60c82a0a", "53a562856dcb6646dc6b74c5d1c3418c6d4dff08c97cd2bed4cb7f88d8c8e589"],
				["6260ce7f461801c34f067ce0f02873a8f1b0e44dfc69752accecd819f38fd8e8", "bc2da82b6fa5b571a7f09049776a1ef7ecd292238051c198c1a84e95b2b4ae17"],
				["e5037de0afc1d8d43d8348414bbf4103043ec8f575bfdc432953cc8d2037fa2d", "4571534baa94d3b5f9f98d09fb990bddbd5f5b03ec481f10e0e5dc841d755bda"],
				["e06372b0f4a207adf5ea905e8f1771b4e7e8dbd1c6a6c5b725866a0ae4fce725", "7a908974bce18cfe12a27bb2ad5a488cd7484a7787104870b27034f94eee31dd"],
				["213c7a715cd5d45358d0bbf9dc0ce02204b10bdde2a3f58540ad6908d0559754", "4b6dad0b5ae462507013ad06245ba190bb4850f5f36a7eeddff2c27534b458f2"],
				["4e7c272a7af4b34e8dbb9352a5419a87e2838c70adc62cddf0cc3a3b08fbd53c", "17749c766c9d0b18e16fd09f6def681b530b9614bff7dd33e0b3941817dcaae6"],
				["fea74e3dbe778b1b10f238ad61686aa5c76e3db2be43057632427e2840fb27b6", "6e0568db9b0b13297cf674deccb6af93126b596b973f7b77701d3db7f23cb96f"],
				["76e64113f677cf0e10a2570d599968d31544e179b760432952c02a4417bdde39", "c90ddf8dee4e95cf577066d70681f0d35e2a33d2b56d2032b4b1752d1901ac01"],
				["c738c56b03b2abe1e8281baa743f8f9a8f7cc643df26cbee3ab150242bcbb891", "893fb578951ad2537f718f2eacbfbbbb82314eef7880cfe917e735d9699a84c3"],
				["d895626548b65b81e264c7637c972877d1d72e5f3a925014372e9f6588f6c14b", "febfaa38f2bc7eae728ec60818c340eb03428d632bb067e179363ed75d7d991f"],
				["b8da94032a957518eb0f6433571e8761ceffc73693e84edd49150a564f676e03", "2804dfa44805a1e4d7c99cc9762808b092cc584d95ff3b511488e4e74efdf6e7"],
				["e80fea14441fb33a7d8adab9475d7fab2019effb5156a792f1a11778e3c0df5d", "eed1de7f638e00771e89768ca3ca94472d155e80af322ea9fcb4291b6ac9ec78"],
				["a301697bdfcd704313ba48e51d567543f2a182031efd6915ddc07bbcc4e16070", "7370f91cfb67e4f5081809fa25d40f9b1735dbf7c0a11a130c0d1a041e177ea1"],
				["90ad85b389d6b936463f9d0512678de208cc330b11307fffab7ac63e3fb04ed4", "e507a3620a38261affdcbd9427222b839aefabe1582894d991d4d48cb6ef150"],
				["8f68b9d2f63b5f339239c1ad981f162ee88c5678723ea3351b7b444c9ec4c0da", "662a9f2dba063986de1d90c2b6be215dbbea2cfe95510bfdf23cbf79501fff82"],
				["e4f3fb0176af85d65ff99ff9198c36091f48e86503681e3e6686fd5053231e11", "1e63633ad0ef4f1c1661a6d0ea02b7286cc7e74ec951d1c9822c38576feb73bc"],
				["8c00fa9b18ebf331eb961537a45a4266c7034f2f0d4e1d0716fb6eae20eae29e", "efa47267fea521a1a9dc343a3736c974c2fadafa81e36c54e7d2a4c66702414b"],
				["e7a26ce69dd4829f3e10cec0a9e98ed3143d084f308b92c0997fddfc60cb3e41", "2a758e300fa7984b471b006a1aafbb18d0a6b2c0420e83e20e8a9421cf2cfd51"],
				["b6459e0ee3662ec8d23540c223bcbdc571cbcb967d79424f3cf29eb3de6b80ef", "67c876d06f3e06de1dadf16e5661db3c4b3ae6d48e35b2ff30bf0b61a71ba45"],
				["d68a80c8280bb840793234aa118f06231d6f1fc67e73c5a5deda0f5b496943e8", "db8ba9fff4b586d00c4b1f9177b0e28b5b0e7b8f7845295a294c84266b133120"],
				["324aed7df65c804252dc0270907a30b09612aeb973449cea4095980fc28d3d5d", "648a365774b61f2ff130c0c35aec1f4f19213b0c7e332843967224af96ab7c84"],
				["4df9c14919cde61f6d51dfdbe5fee5dceec4143ba8d1ca888e8bd373fd054c96", "35ec51092d8728050974c23a1d85d4b5d506cdc288490192ebac06cad10d5d"],
				["9c3919a84a474870faed8a9c1cc66021523489054d7f0308cbfc99c8ac1f98cd", "ddb84f0f4a4ddd57584f044bf260e641905326f76c64c8e6be7e5e03d4fc599d"],
				["6057170b1dd12fdf8de05f281d8e06bb91e1493a8b91d4cc5a21382120a959e5", "9a1af0b26a6a4807add9a2daf71df262465152bc3ee24c65e899be932385a2a8"],
				["a576df8e23a08411421439a4518da31880cef0fba7d4df12b1a6973eecb94266", "40a6bf20e76640b2c92b97afe58cd82c432e10a7f514d9f3ee8be11ae1b28ec8"],
				["7778a78c28dec3e30a05fe9629de8c38bb30d1f5cf9a3a208f763889be58ad71", "34626d9ab5a5b22ff7098e12f2ff580087b38411ff24ac563b513fc1fd9f43ac"],
				["928955ee637a84463729fd30e7afd2ed5f96274e5ad7e5cb09eda9c06d903ac", "c25621003d3f42a827b78a13093a95eeac3d26efa8a8d83fc5180e935bcd091f"],
				["85d0fef3ec6db109399064f3a0e3b2855645b4a907ad354527aae75163d82751", "1f03648413a38c0be29d496e582cf5663e8751e96877331582c237a24eb1f962"],
				["ff2b0dce97eece97c1c9b6041798b85dfdfb6d8882da20308f5404824526087e", "493d13fef524ba188af4c4dc54d07936c7b7ed6fb90e2ceb2c951e01f0c29907"],
				["827fbbe4b1e880ea9ed2b2e6301b212b57f1ee148cd6dd28780e5e2cf856e241", "c60f9c923c727b0b71bef2c67d1d12687ff7a63186903166d605b68baec293ec"],
				["eaa649f21f51bdbae7be4ae34ce6e5217a58fdce7f47f9aa7f3b58fa2120e2b3", "be3279ed5bbbb03ac69a80f89879aa5a01a6b965f13f7e59d47a5305ba5ad93d"],
				["e4a42d43c5cf169d9391df6decf42ee541b6d8f0c9a137401e23632dda34d24f", "4d9f92e716d1c73526fc99ccfb8ad34ce886eedfa8d8e4f13a7f7131deba9414"],
				["1ec80fef360cbdd954160fadab352b6b92b53576a88fea4947173b9d4300bf19", "aeefe93756b5340d2f3a4958a7abbf5e0146e77f6295a07b671cdc1cc107cefd"],
				["146a778c04670c2f91b00af4680dfa8bce3490717d58ba889ddb5928366642be", "b318e0ec3354028add669827f9d4b2870aaa971d2f7e5ed1d0b297483d83efd0"],
				["fa50c0f61d22e5f07e3acebb1aa07b128d0012209a28b9776d76a8793180eef9", "6b84c6922397eba9b72cd2872281a68a5e683293a57a213b38cd8d7d3f4f2811"],
				["da1d61d0ca721a11b1a5bf6b7d88e8421a288ab5d5bba5220e53d32b5f067ec2", "8157f55a7c99306c79c0766161c91e2966a73899d279b48a655fba0f1ad836f1"],
				["a8e282ff0c9706907215ff98e8fd416615311de0446f1e062a73b0610d064e13", "7f97355b8db81c09abfb7f3c5b2515888b679a3e50dd6bd6cef7c73111f4cc0c"],
				["174a53b9c9a285872d39e56e6913cab15d59b1fa512508c022f382de8319497c", "ccc9dc37abfc9c1657b4155f2c47f9e6646b3a1d8cb9854383da13ac079afa73"],
				["959396981943785c3d3e57edf5018cdbe039e730e4918b3d884fdff09475b7ba", "2e7e552888c331dd8ba0386a4b9cd6849c653f64c8709385e9b8abf87524f2fd"],
				["d2a63a50ae401e56d645a1153b109a8fcca0a43d561fba2dbb51340c9d82b151", "e82d86fb6443fcb7565aee58b2948220a70f750af484ca52d4142174dcf89405"],
				["64587e2335471eb890ee7896d7cfdc866bacbdbd3839317b3436f9b45617e073", "d99fcdd5bf6902e2ae96dd6447c299a185b90a39133aeab358299e5e9faf6589"],
				["8481bde0e4e4d885b3a546d3e549de042f0aa6cea250e7fd358d6c86dd45e458", "38ee7b8cba5404dd84a25bf39cecb2ca900a79c42b262e556d64b1b59779057e"],
				["13464a57a78102aa62b6979ae817f4637ffcfed3c4b1ce30bcd6303f6caf666b", "69be159004614580ef7e433453ccb0ca48f300a81d0942e13f495a907f6ecc27"],
				["bc4a9df5b713fe2e9aef430bcc1dc97a0cd9ccede2f28588cada3a0d2d83f366", "d3a81ca6e785c06383937adf4b798caa6e8a9fbfa547b16d758d666581f33c1"],
				["8c28a97bf8298bc0d23d8c749452a32e694b65e30a9472a3954ab30fe5324caa", "40a30463a3305193378fedf31f7cc0eb7ae784f0451cb9459e71dc73cbef9482"],
				["8ea9666139527a8c1dd94ce4f071fd23c8b350c5a4bb33748c4ba111faccae0", "620efabbc8ee2782e24e7c0cfb95c5d735b783be9cf0f8e955af34a30e62b945"],
				["dd3625faef5ba06074669716bbd3788d89bdde815959968092f76cc4eb9a9787", "7a188fa3520e30d461da2501045731ca941461982883395937f68d00c644a573"],
				["f710d79d9eb962297e4f6232b40e8f7feb2bc63814614d692c12de752408221e", "ea98e67232d3b3295d3b535532115ccac8612c721851617526ae47a9c77bfc82"]
			]
		},
		naf: {
			wnd: 7,
			points: [
				["f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9", "388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e672"],
				["2f8bde4d1a07209355b4a7250a5c5128e88b84bddc619ab7cba8d569b240efe4", "d8ac222636e5e3d6d4dba9dda6c9c426f788271bab0d6840dca87d3aa6ac62d6"],
				["5cbdf0646e5db4eaa398f365f2ea7a0e3d419b7e0330e39ce92bddedcac4f9bc", "6aebca40ba255960a3178d6d861a54dba813d0b813fde7b5a5082628087264da"],
				["acd484e2f0c7f65309ad178a9f559abde09796974c57e714c35f110dfc27ccbe", "cc338921b0a7d9fd64380971763b61e9add888a4375f8e0f05cc262ac64f9c37"],
				["774ae7f858a9411e5ef4246b70c65aac5649980be5c17891bbec17895da008cb", "d984a032eb6b5e190243dd56d7b7b365372db1e2dff9d6a8301d74c9c953c61b"],
				["f28773c2d975288bc7d1d205c3748651b075fbc6610e58cddeeddf8f19405aa8", "ab0902e8d880a89758212eb65cdaf473a1a06da521fa91f29b5cb52db03ed81"],
				["d7924d4f7d43ea965a465ae3095ff41131e5946f3c85f79e44adbcf8e27e080e", "581e2872a86c72a683842ec228cc6defea40af2bd896d3a5c504dc9ff6a26b58"],
				["defdea4cdb677750a420fee807eacf21eb9898ae79b9768766e4faa04a2d4a34", "4211ab0694635168e997b0ead2a93daeced1f4a04a95c0f6cfb199f69e56eb77"],
				["2b4ea0a797a443d293ef5cff444f4979f06acfebd7e86d277475656138385b6c", "85e89bc037945d93b343083b5a1c86131a01f60c50269763b570c854e5c09b7a"],
				["352bbf4a4cdd12564f93fa332ce333301d9ad40271f8107181340aef25be59d5", "321eb4075348f534d59c18259dda3e1f4a1b3b2e71b1039c67bd3d8bcf81998c"],
				["2fa2104d6b38d11b0230010559879124e42ab8dfeff5ff29dc9cdadd4ecacc3f", "2de1068295dd865b64569335bd5dd80181d70ecfc882648423ba76b532b7d67"],
				["9248279b09b4d68dab21a9b066edda83263c3d84e09572e269ca0cd7f5453714", "73016f7bf234aade5d1aa71bdea2b1ff3fc0de2a887912ffe54a32ce97cb3402"],
				["daed4f2be3a8bf278e70132fb0beb7522f570e144bf615c07e996d443dee8729", "a69dce4a7d6c98e8d4a1aca87ef8d7003f83c230f3afa726ab40e52290be1c55"],
				["c44d12c7065d812e8acf28d7cbb19f9011ecd9e9fdf281b0e6a3b5e87d22e7db", "2119a460ce326cdc76c45926c982fdac0e106e861edf61c5a039063f0e0e6482"],
				["6a245bf6dc698504c89a20cfded60853152b695336c28063b61c65cbd269e6b4", "e022cf42c2bd4a708b3f5126f16a24ad8b33ba48d0423b6efd5e6348100d8a82"],
				["1697ffa6fd9de627c077e3d2fe541084ce13300b0bec1146f95ae57f0d0bd6a5", "b9c398f186806f5d27561506e4557433a2cf15009e498ae7adee9d63d01b2396"],
				["605bdb019981718b986d0f07e834cb0d9deb8360ffb7f61df982345ef27a7479", "2972d2de4f8d20681a78d93ec96fe23c26bfae84fb14db43b01e1e9056b8c49"],
				["62d14dab4150bf497402fdc45a215e10dcb01c354959b10cfe31c7e9d87ff33d", "80fc06bd8cc5b01098088a1950eed0db01aa132967ab472235f5642483b25eaf"],
				["80c60ad0040f27dade5b4b06c408e56b2c50e9f56b9b8b425e555c2f86308b6f", "1c38303f1cc5c30f26e66bad7fe72f70a65eed4cbe7024eb1aa01f56430bd57a"],
				["7a9375ad6167ad54aa74c6348cc54d344cc5dc9487d847049d5eabb0fa03c8fb", "d0e3fa9eca8726909559e0d79269046bdc59ea10c70ce2b02d499ec224dc7f7"],
				["d528ecd9b696b54c907a9ed045447a79bb408ec39b68df504bb51f459bc3ffc9", "eecf41253136e5f99966f21881fd656ebc4345405c520dbc063465b521409933"],
				["49370a4b5f43412ea25f514e8ecdad05266115e4a7ecb1387231808f8b45963", "758f3f41afd6ed428b3081b0512fd62a54c3f3afbb5b6764b653052a12949c9a"],
				["77f230936ee88cbbd73df930d64702ef881d811e0e1498e2f1c13eb1fc345d74", "958ef42a7886b6400a08266e9ba1b37896c95330d97077cbbe8eb3c7671c60d6"],
				["f2dac991cc4ce4b9ea44887e5c7c0bce58c80074ab9d4dbaeb28531b7739f530", "e0dedc9b3b2f8dad4da1f32dec2531df9eb5fbeb0598e4fd1a117dba703a3c37"],
				["463b3d9f662621fb1b4be8fbbe2520125a216cdfc9dae3debcba4850c690d45b", "5ed430d78c296c3543114306dd8622d7c622e27c970a1de31cb377b01af7307e"],
				["f16f804244e46e2a09232d4aff3b59976b98fac14328a2d1a32496b49998f247", "cedabd9b82203f7e13d206fcdf4e33d92a6c53c26e5cce26d6579962c4e31df6"],
				["caf754272dc84563b0352b7a14311af55d245315ace27c65369e15f7151d41d1", "cb474660ef35f5f2a41b643fa5e460575f4fa9b7962232a5c32f908318a04476"],
				["2600ca4b282cb986f85d0f1709979d8b44a09c07cb86d7c124497bc86f082120", "4119b88753c15bd6a693b03fcddbb45d5ac6be74ab5f0ef44b0be9475a7e4b40"],
				["7635ca72d7e8432c338ec53cd12220bc01c48685e24f7dc8c602a7746998e435", "91b649609489d613d1d5e590f78e6d74ecfc061d57048bad9e76f302c5b9c61"],
				["754e3239f325570cdbbf4a87deee8a66b7f2b33479d468fbc1a50743bf56cc18", "673fb86e5bda30fb3cd0ed304ea49a023ee33d0197a695d0c5d98093c536683"],
				["e3e6bd1071a1e96aff57859c82d570f0330800661d1c952f9fe2694691d9b9e8", "59c9e0bba394e76f40c0aa58379a3cb6a5a2283993e90c4167002af4920e37f5"],
				["186b483d056a033826ae73d88f732985c4ccb1f32ba35f4b4cc47fdcf04aa6eb", "3b952d32c67cf77e2e17446e204180ab21fb8090895138b4a4a797f86e80888b"],
				["df9d70a6b9876ce544c98561f4be4f725442e6d2b737d9c91a8321724ce0963f", "55eb2dafd84d6ccd5f862b785dc39d4ab157222720ef9da217b8c45cf2ba2417"],
				["5edd5cc23c51e87a497ca815d5dce0f8ab52554f849ed8995de64c5f34ce7143", "efae9c8dbc14130661e8cec030c89ad0c13c66c0d17a2905cdc706ab7399a868"],
				["290798c2b6476830da12fe02287e9e777aa3fba1c355b17a722d362f84614fba", "e38da76dcd440621988d00bcf79af25d5b29c094db2a23146d003afd41943e7a"],
				["af3c423a95d9f5b3054754efa150ac39cd29552fe360257362dfdecef4053b45", "f98a3fd831eb2b749a93b0e6f35cfb40c8cd5aa667a15581bc2feded498fd9c6"],
				["766dbb24d134e745cccaa28c99bf274906bb66b26dcf98df8d2fed50d884249a", "744b1152eacbe5e38dcc887980da38b897584a65fa06cedd2c924f97cbac5996"],
				["59dbf46f8c94759ba21277c33784f41645f7b44f6c596a58ce92e666191abe3e", "c534ad44175fbc300f4ea6ce648309a042ce739a7919798cd85e216c4a307f6e"],
				["f13ada95103c4537305e691e74e9a4a8dd647e711a95e73cb62dc6018cfd87b8", "e13817b44ee14de663bf4bc808341f326949e21a6a75c2570778419bdaf5733d"],
				["7754b4fa0e8aced06d4167a2c59cca4cda1869c06ebadfb6488550015a88522c", "30e93e864e669d82224b967c3020b8fa8d1e4e350b6cbcc537a48b57841163a2"],
				["948dcadf5990e048aa3874d46abef9d701858f95de8041d2a6828c99e2262519", "e491a42537f6e597d5d28a3224b1bc25df9154efbd2ef1d2cbba2cae5347d57e"],
				["7962414450c76c1689c7b48f8202ec37fb224cf5ac0bfa1570328a8a3d7c77ab", "100b610ec4ffb4760d5c1fc133ef6f6b12507a051f04ac5760afa5b29db83437"],
				["3514087834964b54b15b160644d915485a16977225b8847bb0dd085137ec47ca", "ef0afbb2056205448e1652c48e8127fc6039e77c15c2378b7e7d15a0de293311"],
				["d3cc30ad6b483e4bc79ce2c9dd8bc54993e947eb8df787b442943d3f7b527eaf", "8b378a22d827278d89c5e9be8f9508ae3c2ad46290358630afb34db04eede0a4"],
				["1624d84780732860ce1c78fcbfefe08b2b29823db913f6493975ba0ff4847610", "68651cf9b6da903e0914448c6cd9d4ca896878f5282be4c8cc06e2a404078575"],
				["733ce80da955a8a26902c95633e62a985192474b5af207da6df7b4fd5fc61cd4", "f5435a2bd2badf7d485a4d8b8db9fcce3e1ef8e0201e4578c54673bc1dc5ea1d"],
				["15d9441254945064cf1a1c33bbd3b49f8966c5092171e699ef258dfab81c045c", "d56eb30b69463e7234f5137b73b84177434800bacebfc685fc37bbe9efe4070d"],
				["a1d0fcf2ec9de675b612136e5ce70d271c21417c9d2b8aaaac138599d0717940", "edd77f50bcb5a3cab2e90737309667f2641462a54070f3d519212d39c197a629"],
				["e22fbe15c0af8ccc5780c0735f84dbe9a790badee8245c06c7ca37331cb36980", "a855babad5cd60c88b430a69f53a1a7a38289154964799be43d06d77d31da06"],
				["311091dd9860e8e20ee13473c1155f5f69635e394704eaa74009452246cfa9b3", "66db656f87d1f04fffd1f04788c06830871ec5a64feee685bd80f0b1286d8374"],
				["34c1fd04d301be89b31c0442d3e6ac24883928b45a9340781867d4232ec2dbdf", "9414685e97b1b5954bd46f730174136d57f1ceeb487443dc5321857ba73abee"],
				["f219ea5d6b54701c1c14de5b557eb42a8d13f3abbcd08affcc2a5e6b049b8d63", "4cb95957e83d40b0f73af4544cccf6b1f4b08d3c07b27fb8d8c2962a400766d1"],
				["d7b8740f74a8fbaab1f683db8f45de26543a5490bca627087236912469a0b448", "fa77968128d9c92ee1010f337ad4717eff15db5ed3c049b3411e0315eaa4593b"],
				["32d31c222f8f6f0ef86f7c98d3a3335ead5bcd32abdd94289fe4d3091aa824bf", "5f3032f5892156e39ccd3d7915b9e1da2e6dac9e6f26e961118d14b8462e1661"],
				["7461f371914ab32671045a155d9831ea8793d77cd59592c4340f86cbc18347b5", "8ec0ba238b96bec0cbdddcae0aa442542eee1ff50c986ea6b39847b3cc092ff6"],
				["ee079adb1df1860074356a25aa38206a6d716b2c3e67453d287698bad7b2b2d6", "8dc2412aafe3be5c4c5f37e0ecc5f9f6a446989af04c4e25ebaac479ec1c8c1e"],
				["16ec93e447ec83f0467b18302ee620f7e65de331874c9dc72bfd8616ba9da6b5", "5e4631150e62fb40d0e8c2a7ca5804a39d58186a50e497139626778e25b0674d"],
				["eaa5f980c245f6f038978290afa70b6bd8855897f98b6aa485b96065d537bd99", "f65f5d3e292c2e0819a528391c994624d784869d7e6ea67fb18041024edc07dc"],
				["78c9407544ac132692ee1910a02439958ae04877151342ea96c4b6b35a49f51", "f3e0319169eb9b85d5404795539a5e68fa1fbd583c064d2462b675f194a3ddb4"],
				["494f4be219a1a77016dcd838431aea0001cdc8ae7a6fc688726578d9702857a5", "42242a969283a5f339ba7f075e36ba2af925ce30d767ed6e55f4b031880d562c"],
				["a598a8030da6d86c6bc7f2f5144ea549d28211ea58faa70ebf4c1e665c1fe9b5", "204b5d6f84822c307e4b4a7140737aec23fc63b65b35f86a10026dbd2d864e6b"],
				["c41916365abb2b5d09192f5f2dbeafec208f020f12570a184dbadc3e58595997", "4f14351d0087efa49d245b328984989d5caf9450f34bfc0ed16e96b58fa9913"],
				["841d6063a586fa475a724604da03bc5b92a2e0d2e0a36acfe4c73a5514742881", "73867f59c0659e81904f9a1c7543698e62562d6744c169ce7a36de01a8d6154"],
				["5e95bb399a6971d376026947f89bde2f282b33810928be4ded112ac4d70e20d5", "39f23f366809085beebfc71181313775a99c9aed7d8ba38b161384c746012865"],
				["36e4641a53948fd476c39f8a99fd974e5ec07564b5315d8bf99471bca0ef2f66", "d2424b1b1abe4eb8164227b085c9aa9456ea13493fd563e06fd51cf5694c78fc"],
				["336581ea7bfbbb290c191a2f507a41cf5643842170e914faeab27c2c579f726", "ead12168595fe1be99252129b6e56b3391f7ab1410cd1e0ef3dcdcabd2fda224"],
				["8ab89816dadfd6b6a1f2634fcf00ec8403781025ed6890c4849742706bd43ede", "6fdcef09f2f6d0a044e654aef624136f503d459c3e89845858a47a9129cdd24e"],
				["1e33f1a746c9c5778133344d9299fcaa20b0938e8acff2544bb40284b8c5fb94", "60660257dd11b3aa9c8ed618d24edff2306d320f1d03010e33a7d2057f3b3b6"],
				["85b7c1dcb3cec1b7ee7f30ded79dd20a0ed1f4cc18cbcfcfa410361fd8f08f31", "3d98a9cdd026dd43f39048f25a8847f4fcafad1895d7a633c6fed3c35e999511"],
				["29df9fbd8d9e46509275f4b125d6d45d7fbe9a3b878a7af872a2800661ac5f51", "b4c4fe99c775a606e2d8862179139ffda61dc861c019e55cd2876eb2a27d84b"],
				["a0b1cae06b0a847a3fea6e671aaf8adfdfe58ca2f768105c8082b2e449fce252", "ae434102edde0958ec4b19d917a6a28e6b72da1834aff0e650f049503a296cf2"],
				["4e8ceafb9b3e9a136dc7ff67e840295b499dfb3b2133e4ba113f2e4c0e121e5", "cf2174118c8b6d7a4b48f6d534ce5c79422c086a63460502b827ce62a326683c"],
				["d24a44e047e19b6f5afb81c7ca2f69080a5076689a010919f42725c2b789a33b", "6fb8d5591b466f8fc63db50f1c0f1c69013f996887b8244d2cdec417afea8fa3"],
				["ea01606a7a6c9cdd249fdfcfacb99584001edd28abbab77b5104e98e8e3b35d4", "322af4908c7312b0cfbfe369f7a7b3cdb7d4494bc2823700cfd652188a3ea98d"],
				["af8addbf2b661c8a6c6328655eb96651252007d8c5ea31be4ad196de8ce2131f", "6749e67c029b85f52a034eafd096836b2520818680e26ac8f3dfbcdb71749700"],
				["e3ae1974566ca06cc516d47e0fb165a674a3dabcfca15e722f0e3450f45889", "2aeabe7e4531510116217f07bf4d07300de97e4874f81f533420a72eeb0bd6a4"],
				["591ee355313d99721cf6993ffed1e3e301993ff3ed258802075ea8ced397e246", "b0ea558a113c30bea60fc4775460c7901ff0b053d25ca2bdeee98f1a4be5d196"],
				["11396d55fda54c49f19aa97318d8da61fa8584e47b084945077cf03255b52984", "998c74a8cd45ac01289d5833a7beb4744ff536b01b257be4c5767bea93ea57a4"],
				["3c5d2a1ba39c5a1790000738c9e0c40b8dcdfd5468754b6405540157e017aa7a", "b2284279995a34e2f9d4de7396fc18b80f9b8b9fdd270f6661f79ca4c81bd257"],
				["cc8704b8a60a0defa3a99a7299f2e9c3fbc395afb04ac078425ef8a1793cc030", "bdd46039feed17881d1e0862db347f8cf395b74fc4bcdc4e940b74e3ac1f1b13"],
				["c533e4f7ea8555aacd9777ac5cad29b97dd4defccc53ee7ea204119b2889b197", "6f0a256bc5efdf429a2fb6242f1a43a2d9b925bb4a4b3a26bb8e0f45eb596096"],
				["c14f8f2ccb27d6f109f6d08d03cc96a69ba8c34eec07bbcf566d48e33da6593", "c359d6923bb398f7fd4473e16fe1c28475b740dd098075e6c0e8649113dc3a38"],
				["a6cbc3046bc6a450bac24789fa17115a4c9739ed75f8f21ce441f72e0b90e6ef", "21ae7f4680e889bb130619e2c0f95a360ceb573c70603139862afd617fa9b9f"],
				["347d6d9a02c48927ebfb86c1359b1caf130a3c0267d11ce6344b39f99d43cc38", "60ea7f61a353524d1c987f6ecec92f086d565ab687870cb12689ff1e31c74448"],
				["da6545d2181db8d983f7dcb375ef5866d47c67b1bf31c8cf855ef7437b72656a", "49b96715ab6878a79e78f07ce5680c5d6673051b4935bd897fea824b77dc208a"],
				["c40747cc9d012cb1a13b8148309c6de7ec25d6945d657146b9d5994b8feb1111", "5ca560753be2a12fc6de6caf2cb489565db936156b9514e1bb5e83037e0fa2d4"],
				["4e42c8ec82c99798ccf3a610be870e78338c7f713348bd34c8203ef4037f3502", "7571d74ee5e0fb92a7a8b33a07783341a5492144cc54bcc40a94473693606437"],
				["3775ab7089bc6af823aba2e1af70b236d251cadb0c86743287522a1b3b0dedea", "be52d107bcfa09d8bcb9736a828cfa7fac8db17bf7a76a2c42ad961409018cf7"],
				["cee31cbf7e34ec379d94fb814d3d775ad954595d1314ba8846959e3e82f74e26", "8fd64a14c06b589c26b947ae2bcf6bfa0149ef0be14ed4d80f448a01c43b1c6d"],
				["b4f9eaea09b6917619f6ea6a4eb5464efddb58fd45b1ebefcdc1a01d08b47986", "39e5c9925b5a54b07433a4f18c61726f8bb131c012ca542eb24a8ac07200682a"],
				["d4263dfc3d2df923a0179a48966d30ce84e2515afc3dccc1b77907792ebcc60e", "62dfaf07a0f78feb30e30d6295853ce189e127760ad6cf7fae164e122a208d54"],
				["48457524820fa65a4f8d35eb6930857c0032acc0a4a2de422233eeda897612c4", "25a748ab367979d98733c38a1fa1c2e7dc6cc07db2d60a9ae7a76aaa49bd0f77"],
				["dfeeef1881101f2cb11644f3a2afdfc2045e19919152923f367a1767c11cceda", "ecfb7056cf1de042f9420bab396793c0c390bde74b4bbdff16a83ae09a9a7517"],
				["6d7ef6b17543f8373c573f44e1f389835d89bcbc6062ced36c82df83b8fae859", "cd450ec335438986dfefa10c57fea9bcc521a0959b2d80bbf74b190dca712d10"],
				["e75605d59102a5a2684500d3b991f2e3f3c88b93225547035af25af66e04541f", "f5c54754a8f71ee540b9b48728473e314f729ac5308b06938360990e2bfad125"],
				["eb98660f4c4dfaa06a2be453d5020bc99a0c2e60abe388457dd43fefb1ed620c", "6cb9a8876d9cb8520609af3add26cd20a0a7cd8a9411131ce85f44100099223e"],
				["13e87b027d8514d35939f2e6892b19922154596941888336dc3563e3b8dba942", "fef5a3c68059a6dec5d624114bf1e91aac2b9da568d6abeb2570d55646b8adf1"],
				["ee163026e9fd6fe017c38f06a5be6fc125424b371ce2708e7bf4491691e5764a", "1acb250f255dd61c43d94ccc670d0f58f49ae3fa15b96623e5430da0ad6c62b2"],
				["b268f5ef9ad51e4d78de3a750c2dc89b1e626d43505867999932e5db33af3d80", "5f310d4b3c99b9ebb19f77d41c1dee018cf0d34fd4191614003e945a1216e423"],
				["ff07f3118a9df035e9fad85eb6c7bfe42b02f01ca99ceea3bf7ffdba93c4750d", "438136d603e858a3a5c440c38eccbaddc1d2942114e2eddd4740d098ced1f0d8"],
				["8d8b9855c7c052a34146fd20ffb658bea4b9f69e0d825ebec16e8c3ce2b526a1", "cdb559eedc2d79f926baf44fb84ea4d44bcf50fee51d7ceb30e2e7f463036758"],
				["52db0b5384dfbf05bfa9d472d7ae26dfe4b851ceca91b1eba54263180da32b63", "c3b997d050ee5d423ebaf66a6db9f57b3180c902875679de924b69d84a7b375"],
				["e62f9490d3d51da6395efd24e80919cc7d0f29c3f3fa48c6fff543becbd43352", "6d89ad7ba4876b0b22c2ca280c682862f342c8591f1daf5170e07bfd9ccafa7d"],
				["7f30ea2476b399b4957509c88f77d0191afa2ff5cb7b14fd6d8e7d65aaab1193", "ca5ef7d4b231c94c3b15389a5f6311e9daff7bb67b103e9880ef4bff637acaec"],
				["5098ff1e1d9f14fb46a210fada6c903fef0fb7b4a1dd1d9ac60a0361800b7a00", "9731141d81fc8f8084d37c6e7542006b3ee1b40d60dfe5362a5b132fd17ddc0"],
				["32b78c7de9ee512a72895be6b9cbefa6e2f3c4ccce445c96b9f2c81e2778ad58", "ee1849f513df71e32efc3896ee28260c73bb80547ae2275ba497237794c8753c"],
				["e2cb74fddc8e9fbcd076eef2a7c72b0ce37d50f08269dfc074b581550547a4f7", "d3aa2ed71c9dd2247a62df062736eb0baddea9e36122d2be8641abcb005cc4a4"],
				["8438447566d4d7bedadc299496ab357426009a35f235cb141be0d99cd10ae3a8", "c4e1020916980a4da5d01ac5e6ad330734ef0d7906631c4f2390426b2edd791f"],
				["4162d488b89402039b584c6fc6c308870587d9c46f660b878ab65c82c711d67e", "67163e903236289f776f22c25fb8a3afc1732f2b84b4e95dbda47ae5a0852649"],
				["3fad3fa84caf0f34f0f89bfd2dcf54fc175d767aec3e50684f3ba4a4bf5f683d", "cd1bc7cb6cc407bb2f0ca647c718a730cf71872e7d0d2a53fa20efcdfe61826"],
				["674f2600a3007a00568c1a7ce05d0816c1fb84bf1370798f1c69532faeb1a86b", "299d21f9413f33b3edf43b257004580b70db57da0b182259e09eecc69e0d38a5"],
				["d32f4da54ade74abb81b815ad1fb3b263d82d6c692714bcff87d29bd5ee9f08f", "f9429e738b8e53b968e99016c059707782e14f4535359d582fc416910b3eea87"],
				["30e4e670435385556e593657135845d36fbb6931f72b08cb1ed954f1e3ce3ff6", "462f9bce619898638499350113bbc9b10a878d35da70740dc695a559eb88db7b"],
				["be2062003c51cc3004682904330e4dee7f3dcd10b01e580bf1971b04d4cad297", "62188bc49d61e5428573d48a74e1c655b1c61090905682a0d5558ed72dccb9bc"],
				["93144423ace3451ed29e0fb9ac2af211cb6e84a601df5993c419859fff5df04a", "7c10dfb164c3425f5c71a3f9d7992038f1065224f72bb9d1d902a6d13037b47c"],
				["b015f8044f5fcbdcf21ca26d6c34fb8197829205c7b7d2a7cb66418c157b112c", "ab8c1e086d04e813744a655b2df8d5f83b3cdc6faa3088c1d3aea1454e3a1d5f"],
				["d5e9e1da649d97d89e4868117a465a3a4f8a18de57a140d36b3f2af341a21b52", "4cb04437f391ed73111a13cc1d4dd0db1693465c2240480d8955e8592f27447a"],
				["d3ae41047dd7ca065dbf8ed77b992439983005cd72e16d6f996a5316d36966bb", "bd1aeb21ad22ebb22a10f0303417c6d964f8cdd7df0aca614b10dc14d125ac46"],
				["463e2763d885f958fc66cdd22800f0a487197d0a82e377b49f80af87c897b065", "bfefacdb0e5d0fd7df3a311a94de062b26b80c61fbc97508b79992671ef7ca7f"],
				["7985fdfd127c0567c6f53ec1bb63ec3158e597c40bfe747c83cddfc910641917", "603c12daf3d9862ef2b25fe1de289aed24ed291e0ec6708703a5bd567f32ed03"],
				["74a1ad6b5f76e39db2dd249410eac7f99e74c59cb83d2d0ed5ff1543da7703e9", "cc6157ef18c9c63cd6193d83631bbea0093e0968942e8c33d5737fd790e0db08"],
				["30682a50703375f602d416664ba19b7fc9bab42c72747463a71d0896b22f6da3", "553e04f6b018b4fa6c8f39e7f311d3176290d0e0f19ca73f17714d9977a22ff8"],
				["9e2158f0d7c0d5f26c3791efefa79597654e7a2b2464f52b1ee6c1347769ef57", "712fcdd1b9053f09003a3481fa7762e9ffd7c8ef35a38509e2fbf2629008373"],
				["176e26989a43c9cfeba4029c202538c28172e566e3c4fce7322857f3be327d66", "ed8cc9d04b29eb877d270b4878dc43c19aefd31f4eee09ee7b47834c1fa4b1c3"],
				["75d46efea3771e6e68abb89a13ad747ecf1892393dfc4f1b7004788c50374da8", "9852390a99507679fd0b86fd2b39a868d7efc22151346e1a3ca4726586a6bed8"],
				["809a20c67d64900ffb698c4c825f6d5f2310fb0451c869345b7319f645605721", "9e994980d9917e22b76b061927fa04143d096ccc54963e6a5ebfa5f3f8e286c1"],
				["1b38903a43f7f114ed4500b4eac7083fdefece1cf29c63528d563446f972c180", "4036edc931a60ae889353f77fd53de4a2708b26b6f5da72ad3394119daf408f9"]
			]
		}
	};
})), Ns = /* @__PURE__ */ s(((e) => {
	var t = e, n = js(), r = ys(), i = fs().assert;
	function a(e) {
		e.type === "short" ? this.curve = new r.short(e) : e.type === "edwards" ? this.curve = new r.edwards(e) : this.curve = new r.mont(e), this.g = this.curve.g, this.n = this.curve.n, this.hash = e.hash, i(this.g.validate(), "Invalid curve"), i(this.g.mul(this.n).isInfinity(), "Invalid curve, G*N != O");
	}
	t.PresetCurve = a;
	function o(e, n) {
		Object.defineProperty(t, e, {
			configurable: !0,
			enumerable: !0,
			get: function() {
				var r = new a(n);
				return Object.defineProperty(t, e, {
					configurable: !0,
					enumerable: !0,
					value: r
				}), r;
			}
		});
	}
	o("p192", {
		type: "short",
		prime: "p192",
		p: "ffffffff ffffffff ffffffff fffffffe ffffffff ffffffff",
		a: "ffffffff ffffffff ffffffff fffffffe ffffffff fffffffc",
		b: "64210519 e59c80e7 0fa7e9ab 72243049 feb8deec c146b9b1",
		n: "ffffffff ffffffff ffffffff 99def836 146bc9b1 b4d22831",
		hash: n.sha256,
		gRed: !1,
		g: ["188da80e b03090f6 7cbf20eb 43a18800 f4ff0afd 82ff1012", "07192b95 ffc8da78 631011ed 6b24cdd5 73f977a1 1e794811"]
	}), o("p224", {
		type: "short",
		prime: "p224",
		p: "ffffffff ffffffff ffffffff ffffffff 00000000 00000000 00000001",
		a: "ffffffff ffffffff ffffffff fffffffe ffffffff ffffffff fffffffe",
		b: "b4050a85 0c04b3ab f5413256 5044b0b7 d7bfd8ba 270b3943 2355ffb4",
		n: "ffffffff ffffffff ffffffff ffff16a2 e0b8f03e 13dd2945 5c5c2a3d",
		hash: n.sha256,
		gRed: !1,
		g: ["b70e0cbd 6bb4bf7f 321390b9 4a03c1d3 56c21122 343280d6 115c1d21", "bd376388 b5f723fb 4c22dfe6 cd4375a0 5a074764 44d58199 85007e34"]
	}), o("p256", {
		type: "short",
		prime: null,
		p: "ffffffff 00000001 00000000 00000000 00000000 ffffffff ffffffff ffffffff",
		a: "ffffffff 00000001 00000000 00000000 00000000 ffffffff ffffffff fffffffc",
		b: "5ac635d8 aa3a93e7 b3ebbd55 769886bc 651d06b0 cc53b0f6 3bce3c3e 27d2604b",
		n: "ffffffff 00000000 ffffffff ffffffff bce6faad a7179e84 f3b9cac2 fc632551",
		hash: n.sha256,
		gRed: !1,
		g: ["6b17d1f2 e12c4247 f8bce6e5 63a440f2 77037d81 2deb33a0 f4a13945 d898c296", "4fe342e2 fe1a7f9b 8ee7eb4a 7c0f9e16 2bce3357 6b315ece cbb64068 37bf51f5"]
	}), o("p384", {
		type: "short",
		prime: null,
		p: "ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffe ffffffff 00000000 00000000 ffffffff",
		a: "ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffe ffffffff 00000000 00000000 fffffffc",
		b: "b3312fa7 e23ee7e4 988e056b e3f82d19 181d9c6e fe814112 0314088f 5013875a c656398d 8a2ed19d 2a85c8ed d3ec2aef",
		n: "ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff c7634d81 f4372ddf 581a0db2 48b0a77a ecec196a ccc52973",
		hash: n.sha384,
		gRed: !1,
		g: ["aa87ca22 be8b0537 8eb1c71e f320ad74 6e1d3b62 8ba79b98 59f741e0 82542a38 5502f25d bf55296c 3a545e38 72760ab7", "3617de4a 96262c6f 5d9e98bf 9292dc29 f8f41dbd 289a147c e9da3113 b5f0b8c0 0a60b1ce 1d7e819d 7a431d7c 90ea0e5f"]
	}), o("p521", {
		type: "short",
		prime: null,
		p: "000001ff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff",
		a: "000001ff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffc",
		b: "00000051 953eb961 8e1c9a1f 929a21a0 b68540ee a2da725b 99b315f3 b8b48991 8ef109e1 56193951 ec7e937b 1652c0bd 3bb1bf07 3573df88 3d2c34f1 ef451fd4 6b503f00",
		n: "000001ff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffa 51868783 bf2f966b 7fcc0148 f709a5d0 3bb5c9b8 899c47ae bb6fb71e 91386409",
		hash: n.sha512,
		gRed: !1,
		g: ["000000c6 858e06b7 0404e9cd 9e3ecb66 2395b442 9c648139 053fb521 f828af60 6b4d3dba a14b5e77 efe75928 fe1dc127 a2ffa8de 3348b3c1 856a429b f97e7e31 c2e5bd66", "00000118 39296a78 9a3bc004 5c8a5fb4 2c7d1bd9 98f54449 579b4468 17afbd17 273e662c 97ee7299 5ef42640 c550b901 3fad0761 353c7086 a272c240 88be9476 9fd16650"]
	}), o("curve25519", {
		type: "mont",
		prime: "p25519",
		p: "7fffffffffffffff ffffffffffffffff ffffffffffffffff ffffffffffffffed",
		a: "76d06",
		b: "1",
		n: "1000000000000000 0000000000000000 14def9dea2f79cd6 5812631a5cf5d3ed",
		hash: n.sha256,
		gRed: !1,
		g: ["9"]
	}), o("ed25519", {
		type: "edwards",
		prime: "p25519",
		p: "7fffffffffffffff ffffffffffffffff ffffffffffffffff ffffffffffffffed",
		a: "-1",
		c: "1",
		d: "52036cee2b6ffe73 8cc740797779e898 00700a4d4141d8ab 75eb4dca135978a3",
		n: "1000000000000000 0000000000000000 14def9dea2f79cd6 5812631a5cf5d3ed",
		hash: n.sha256,
		gRed: !1,
		g: ["216936d3cd6e53fec0a4e231fdd6dc5c692cc7609525a7b2c9562d608f25d51a", "6666666666666666666666666666666666666666666666666666666666666658"]
	});
	var s;
	try {
		s = Ms();
	} catch {
		s = void 0;
	}
	o("secp256k1", {
		type: "short",
		prime: "k256",
		p: "ffffffff ffffffff ffffffff ffffffff ffffffff ffffffff fffffffe fffffc2f",
		a: "0",
		b: "7",
		n: "ffffffff ffffffff ffffffff fffffffe baaedce6 af48a03b bfd25e8c d0364141",
		h: "1",
		hash: n.sha256,
		beta: "7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee",
		lambda: "5363ad4cc05c30e0a5261c028812645a122e22ea20816678df02967c1b23bd72",
		basis: [{
			a: "3086d221a7d46bcde86c90e49284eb15",
			b: "-e4437ed6010e88286f547fa90abfe4c3"
		}, {
			a: "114ca50f7a8e2f3f657c1108d9d44cfd8",
			b: "3086d221a7d46bcde86c90e49284eb15"
		}],
		gRed: !1,
		g: [
			"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
			"483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",
			s
		]
	});
})), Ps = /* @__PURE__ */ s(((e, t) => {
	var n = js(), r = ds(), i = us();
	function a(e) {
		if (!(this instanceof a)) return new a(e);
		this.hash = e.hash, this.predResist = !!e.predResist, this.outLen = this.hash.outSize, this.minEntropy = e.minEntropy || this.hash.hmacStrength, this._reseed = null, this.reseedInterval = null, this.K = null, this.V = null;
		var t = r.toArray(e.entropy, e.entropyEnc || "hex"), n = r.toArray(e.nonce, e.nonceEnc || "hex"), o = r.toArray(e.pers, e.persEnc || "hex");
		i(t.length >= this.minEntropy / 8, "Not enough entropy. Minimum is: " + this.minEntropy + " bits"), this._init(t, n, o);
	}
	t.exports = a, a.prototype._init = function(e, t, n) {
		var r = e.concat(t).concat(n);
		this.K = Array(this.outLen / 8), this.V = Array(this.outLen / 8);
		for (var i = 0; i < this.V.length; i++) this.K[i] = 0, this.V[i] = 1;
		this._update(r), this._reseed = 1, this.reseedInterval = 281474976710656;
	}, a.prototype._hmac = function() {
		return new n.hmac(this.hash, this.K);
	}, a.prototype._update = function(e) {
		var t = this._hmac().update(this.V).update([0]);
		e && (t = t.update(e)), this.K = t.digest(), this.V = this._hmac().update(this.V).digest(), e && (this.K = this._hmac().update(this.V).update([1]).update(e).digest(), this.V = this._hmac().update(this.V).digest());
	}, a.prototype.reseed = function(e, t, n, a) {
		typeof t != "string" && (a = n, n = t, t = null), e = r.toArray(e, t), n = r.toArray(n, a), i(e.length >= this.minEntropy / 8, "Not enough entropy. Minimum is: " + this.minEntropy + " bits"), this._update(e.concat(n || [])), this._reseed = 1;
	}, a.prototype.generate = function(e, t, n, i) {
		if (this._reseed > this.reseedInterval) throw Error("Reseed is required");
		typeof t != "string" && (i = n, n = t, t = null), n && (n = r.toArray(n, i || "hex"), this._update(n));
		for (var a = []; a.length < e;) this.V = this._hmac().update(this.V).digest(), a = a.concat(this.V);
		var o = a.slice(0, e);
		return this._update(n), this._reseed++, r.encode(o, t);
	};
})), Fs = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = fs().assert;
	function i(e, t) {
		this.ec = e, this.priv = null, this.pub = null, t.priv && this._importPrivate(t.priv, t.privEnc), t.pub && this._importPublic(t.pub, t.pubEnc);
	}
	t.exports = i, i.fromPublic = function(e, t, n) {
		return t instanceof i ? t : new i(e, {
			pub: t,
			pubEnc: n
		});
	}, i.fromPrivate = function(e, t, n) {
		return t instanceof i ? t : new i(e, {
			priv: t,
			privEnc: n
		});
	}, i.prototype.validate = function() {
		var e = this.getPublic();
		return e.isInfinity() ? {
			result: !1,
			reason: "Invalid public key"
		} : e.validate() ? e.mul(this.ec.curve.n).isInfinity() ? {
			result: !0,
			reason: null
		} : {
			result: !1,
			reason: "Public key * N != O"
		} : {
			result: !1,
			reason: "Public key is not a point"
		};
	}, i.prototype.getPublic = function(e, t) {
		return typeof e == "string" && (t = e, e = null), this.pub ||= this.ec.g.mul(this.priv), t ? this.pub.encode(t, e) : this.pub;
	}, i.prototype.getPrivate = function(e) {
		return e === "hex" ? this.priv.toString(16, 2) : this.priv;
	}, i.prototype._importPrivate = function(e, t) {
		this.priv = new n(e, t || 16), this.priv = this.priv.umod(this.ec.curve.n);
	}, i.prototype._importPublic = function(e, t) {
		if (e.x || e.y) {
			this.ec.curve.type === "mont" ? r(e.x, "Need x coordinate") : (this.ec.curve.type === "short" || this.ec.curve.type === "edwards") && r(e.x && e.y, "Need both x and y coordinate"), this.pub = this.ec.curve.point(e.x, e.y);
			return;
		}
		this.pub = this.ec.curve.decodePoint(e, t);
	}, i.prototype.derive = function(e) {
		return e.validate() || r(e.validate(), "public point not validated"), e.mul(this.priv).getX();
	}, i.prototype.sign = function(e, t, n) {
		return this.ec.sign(e, this, t, n);
	}, i.prototype.verify = function(e, t, n) {
		return this.ec.verify(e, t, this, void 0, n);
	}, i.prototype.inspect = function() {
		return "<Key priv: " + (this.priv && this.priv.toString(16, 2)) + " pub: " + (this.pub && this.pub.inspect()) + " >";
	};
})), Is = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = fs(), i = r.assert;
	function a(e, t) {
		if (e instanceof a) return e;
		this._importDER(e, t) || (i(e.r && e.s, "Signature without r or s"), this.r = new n(e.r, 16), this.s = new n(e.s, 16), e.recoveryParam === void 0 ? this.recoveryParam = null : this.recoveryParam = e.recoveryParam);
	}
	t.exports = a;
	function o() {
		this.place = 0;
	}
	function s(e, t) {
		var n = e[t.place++];
		if (!(n & 128)) return n;
		var r = n & 15;
		if (r === 0 || r > 4 || e[t.place] === 0) return !1;
		for (var i = 0, a = 0, o = t.place; a < r; a++, o++) i <<= 8, i |= e[o], i >>>= 0;
		return i <= 127 ? !1 : (t.place = o, i);
	}
	function c(e) {
		for (var t = 0, n = e.length - 1; !e[t] && !(e[t + 1] & 128) && t < n;) t++;
		return t === 0 ? e : e.slice(t);
	}
	a.prototype._importDER = function(e, t) {
		e = r.toArray(e, t);
		var i = new o();
		if (e[i.place++] !== 48) return !1;
		var a = s(e, i);
		if (a === !1 || a + i.place !== e.length || e[i.place++] !== 2) return !1;
		var c = s(e, i);
		if (c === !1 || e[i.place] & 128) return !1;
		var l = e.slice(i.place, c + i.place);
		if (i.place += c, e[i.place++] !== 2) return !1;
		var u = s(e, i);
		if (u === !1 || e.length !== u + i.place || e[i.place] & 128) return !1;
		var d = e.slice(i.place, u + i.place);
		if (l[0] === 0) if (l[1] & 128) l = l.slice(1);
		else return !1;
		if (d[0] === 0) if (d[1] & 128) d = d.slice(1);
		else return !1;
		return this.r = new n(l), this.s = new n(d), this.recoveryParam = null, !0;
	};
	function l(e, t) {
		if (t < 128) {
			e.push(t);
			return;
		}
		var n = 1 + (Math.log(t) / Math.LN2 >>> 3);
		for (e.push(n | 128); --n;) e.push(t >>> (n << 3) & 255);
		e.push(t);
	}
	a.prototype.toDER = function(e) {
		var t = this.r.toArray(), n = this.s.toArray();
		for (t[0] & 128 && (t = [0].concat(t)), n[0] & 128 && (n = [0].concat(n)), t = c(t), n = c(n); !n[0] && !(n[1] & 128);) n = n.slice(1);
		var i = [2];
		l(i, t.length), i = i.concat(t), i.push(2), l(i, n.length);
		var a = i.concat(n), o = [48];
		return l(o, a.length), o = o.concat(a), r.encode(o, e);
	};
})), Ls = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = Ps(), i = fs(), a = Ns(), o = ps(), s = i.assert, c = Fs(), l = Is();
	function u(e) {
		if (!(this instanceof u)) return new u(e);
		typeof e == "string" && (s(Object.prototype.hasOwnProperty.call(a, e), "Unknown curve " + e), e = a[e]), e instanceof a.PresetCurve && (e = { curve: e }), this.curve = e.curve.curve, this.n = this.curve.n, this.nh = this.n.ushrn(1), this.g = this.curve.g, this.g = e.curve.g, this.g.precompute(e.curve.n.bitLength() + 1), this.hash = e.hash || e.curve.hash;
	}
	t.exports = u, u.prototype.keyPair = function(e) {
		return new c(this, e);
	}, u.prototype.keyFromPrivate = function(e, t) {
		return c.fromPrivate(this, e, t);
	}, u.prototype.keyFromPublic = function(e, t) {
		return c.fromPublic(this, e, t);
	}, u.prototype.genKeyPair = function(e) {
		e ||= {};
		for (var t = new r({
			hash: this.hash,
			pers: e.pers,
			persEnc: e.persEnc || "utf8",
			entropy: e.entropy || o(this.hash.hmacStrength),
			entropyEnc: e.entropy && e.entropyEnc || "utf8",
			nonce: this.n.toArray()
		}), i = this.n.byteLength(), a = this.n.sub(new n(2));;) {
			var s = new n(t.generate(i));
			if (!(s.cmp(a) > 0)) return s.iaddn(1), this.keyFromPrivate(s);
		}
	}, u.prototype._truncateToN = function(e, t, r) {
		var i;
		if (n.isBN(e) || typeof e == "number") e = new n(e, 16), i = e.byteLength();
		else if (typeof e == "object") i = e.length, e = new n(e, 16);
		else {
			var a = e.toString();
			i = a.length + 1 >>> 1, e = new n(a, 16);
		}
		typeof r != "number" && (r = i * 8);
		var o = r - this.n.bitLength();
		return o > 0 && (e = e.ushrn(o)), !t && e.cmp(this.n) >= 0 ? e.sub(this.n) : e;
	}, u.prototype.sign = function(e, t, i, a) {
		if (typeof i == "object" && (a = i, i = null), a ||= {}, typeof e != "string" && typeof e != "number" && !n.isBN(e)) {
			s(typeof e == "object" && e && typeof e.length == "number", "Expected message to be an array-like, a hex string, or a BN instance"), s(e.length >>> 0 === e.length);
			for (var o = 0; o < e.length; o++) s((e[o] & 255) === e[o]);
		}
		t = this.keyFromPrivate(t, i), e = this._truncateToN(e, !1, a.msgBitLength), s(!e.isNeg(), "Can not sign a negative message");
		var c = this.n.byteLength(), u = t.getPrivate().toArray("be", c), d = e.toArray("be", c);
		s(new n(d).eq(e), "Can not sign message");
		for (var f = new r({
			hash: this.hash,
			entropy: u,
			nonce: d,
			pers: a.pers,
			persEnc: a.persEnc || "utf8"
		}), p = this.n.sub(new n(1)), m = 0;; m++) {
			var h = a.k ? a.k(m) : new n(f.generate(this.n.byteLength()));
			if (h = this._truncateToN(h, !0), !(h.cmpn(1) <= 0 || h.cmp(p) >= 0)) {
				var g = this.g.mul(h);
				if (!g.isInfinity()) {
					var _ = g.getX(), v = _.umod(this.n);
					if (v.cmpn(0) !== 0) {
						var y = h.invm(this.n).mul(v.mul(t.getPrivate()).iadd(e));
						if (y = y.umod(this.n), y.cmpn(0) !== 0) {
							var b = (g.getY().isOdd() ? 1 : 0) | (_.cmp(v) === 0 ? 0 : 2);
							return a.canonical && y.cmp(this.nh) > 0 && (y = this.n.sub(y), b ^= 1), new l({
								r: v,
								s: y,
								recoveryParam: b
							});
						}
					}
				}
			}
		}
	}, u.prototype.verify = function(e, t, n, r, i) {
		i ||= {}, e = this._truncateToN(e, !1, i.msgBitLength), n = this.keyFromPublic(n, r), t = new l(t, "hex");
		var a = t.r, o = t.s;
		if (a.cmpn(1) < 0 || a.cmp(this.n) >= 0 || o.cmpn(1) < 0 || o.cmp(this.n) >= 0) return !1;
		var s = o.invm(this.n), c = s.mul(e).umod(this.n), u = s.mul(a).umod(this.n), d;
		return this.curve._maxwellTrick ? (d = this.g.jmulAdd(c, n.getPublic(), u), d.isInfinity() ? !1 : d.eqXToP(a)) : (d = this.g.mulAdd(c, n.getPublic(), u), d.isInfinity() ? !1 : d.getX().umod(this.n).cmp(a) === 0);
	}, u.prototype.recoverPubKey = function(e, t, r, i) {
		s((3 & r) === r, "The recovery param is more than two bits"), t = new l(t, i);
		var a = this.n, o = new n(e), c = t.r, u = t.s, d = r & 1, f = r >> 1;
		if (c.cmp(this.curve.p.umod(this.curve.n)) >= 0 && f) throw Error("Unable to find sencond key candinate");
		c = f ? this.curve.pointFromX(c.add(this.curve.n), d) : this.curve.pointFromX(c, d);
		var p = t.r.invm(a), m = a.sub(o).mul(p).umod(a), h = u.mul(p).umod(a);
		return this.g.mulAdd(m, c, h);
	}, u.prototype.getKeyRecoveryParam = function(e, t, n, r) {
		if (t = new l(t, r), t.recoveryParam !== null) return t.recoveryParam;
		for (var i = 0; i < 4; i++) {
			var a;
			try {
				a = this.recoverPubKey(e, t, i);
			} catch {
				continue;
			}
			if (a.eq(n)) return i;
		}
		throw Error("Unable to find valid recovery factor");
	};
})), Rs = /* @__PURE__ */ s(((e, t) => {
	var n = fs(), r = n.assert, i = n.parseBytes, a = n.cachedProperty;
	function o(e, t) {
		this.eddsa = e, this._secret = i(t.secret), e.isPoint(t.pub) ? this._pub = t.pub : this._pubBytes = i(t.pub);
	}
	o.fromPublic = function(e, t) {
		return t instanceof o ? t : new o(e, { pub: t });
	}, o.fromSecret = function(e, t) {
		return t instanceof o ? t : new o(e, { secret: t });
	}, o.prototype.secret = function() {
		return this._secret;
	}, a(o, "pubBytes", function() {
		return this.eddsa.encodePoint(this.pub());
	}), a(o, "pub", function() {
		return this._pubBytes ? this.eddsa.decodePoint(this._pubBytes) : this.eddsa.g.mul(this.priv());
	}), a(o, "privBytes", function() {
		var e = this.eddsa, t = this.hash(), n = e.encodingLength - 1, r = t.slice(0, e.encodingLength);
		return r[0] &= 248, r[n] &= 127, r[n] |= 64, r;
	}), a(o, "priv", function() {
		return this.eddsa.decodeInt(this.privBytes());
	}), a(o, "hash", function() {
		return this.eddsa.hash().update(this.secret()).digest();
	}), a(o, "messagePrefix", function() {
		return this.hash().slice(this.eddsa.encodingLength);
	}), o.prototype.sign = function(e) {
		return r(this._secret, "KeyPair can only verify"), this.eddsa.sign(e, this);
	}, o.prototype.verify = function(e, t) {
		return this.eddsa.verify(e, t, this);
	}, o.prototype.getSecret = function(e) {
		return r(this._secret, "KeyPair is public only"), n.encode(this.secret(), e);
	}, o.prototype.getPublic = function(e) {
		return n.encode(this.pubBytes(), e);
	}, t.exports = o;
})), zs = /* @__PURE__ */ s(((e, t) => {
	var n = ls(), r = fs(), i = r.assert, a = r.cachedProperty, o = r.parseBytes;
	function s(e, t) {
		this.eddsa = e, typeof t != "object" && (t = o(t)), Array.isArray(t) && (i(t.length === e.encodingLength * 2, "Signature has invalid size"), t = {
			R: t.slice(0, e.encodingLength),
			S: t.slice(e.encodingLength)
		}), i(t.R && t.S, "Signature without R or S"), e.isPoint(t.R) && (this._R = t.R), t.S instanceof n && (this._S = t.S), this._Rencoded = Array.isArray(t.R) ? t.R : t.Rencoded, this._Sencoded = Array.isArray(t.S) ? t.S : t.Sencoded;
	}
	a(s, "S", function() {
		return this.eddsa.decodeInt(this.Sencoded());
	}), a(s, "R", function() {
		return this.eddsa.decodePoint(this.Rencoded());
	}), a(s, "Rencoded", function() {
		return this.eddsa.encodePoint(this.R());
	}), a(s, "Sencoded", function() {
		return this.eddsa.encodeInt(this.S());
	}), s.prototype.toBytes = function() {
		return this.Rencoded().concat(this.Sencoded());
	}, s.prototype.toHex = function() {
		return r.encode(this.toBytes(), "hex").toUpperCase();
	}, t.exports = s;
})), Bs = /* @__PURE__ */ s(((e, t) => {
	var n = js(), r = Ns(), i = fs(), a = i.assert, o = i.parseBytes, s = Rs(), c = zs();
	function l(e) {
		if (a(e === "ed25519", "only tested with ed25519 so far"), !(this instanceof l)) return new l(e);
		e = r[e].curve, this.curve = e, this.g = e.g, this.g.precompute(e.n.bitLength() + 1), this.pointClass = e.point().constructor, this.encodingLength = Math.ceil(e.n.bitLength() / 8), this.hash = n.sha512;
	}
	t.exports = l, l.prototype.sign = function(e, t) {
		e = o(e);
		var n = this.keyFromSecret(t), r = this.hashInt(n.messagePrefix(), e), i = this.g.mul(r), a = this.encodePoint(i), s = this.hashInt(a, n.pubBytes(), e).mul(n.priv()), c = r.add(s).umod(this.curve.n);
		return this.makeSignature({
			R: i,
			S: c,
			Rencoded: a
		});
	}, l.prototype.verify = function(e, t, n) {
		if (e = o(e), t = this.makeSignature(t), t.S().gte(t.eddsa.curve.n) || t.S().isNeg()) return !1;
		var r = this.keyFromPublic(n), i = this.hashInt(t.Rencoded(), r.pubBytes(), e), a = this.g.mul(t.S());
		return t.R().add(r.pub().mul(i)).eq(a);
	}, l.prototype.hashInt = function() {
		for (var e = this.hash(), t = 0; t < arguments.length; t++) e.update(arguments[t]);
		return i.intFromLE(e.digest()).umod(this.curve.n);
	}, l.prototype.keyFromPublic = function(e) {
		return s.fromPublic(this, e);
	}, l.prototype.keyFromSecret = function(e) {
		return s.fromSecret(this, e);
	}, l.prototype.makeSignature = function(e) {
		return e instanceof c ? e : new c(this, e);
	}, l.prototype.encodePoint = function(e) {
		var t = e.getY().toArray("le", this.encodingLength);
		return t[this.encodingLength - 1] |= e.getX().isOdd() ? 128 : 0, t;
	}, l.prototype.decodePoint = function(e) {
		e = i.parseBytes(e);
		var t = e.length - 1, n = e.slice(0, t).concat(e[t] & -129), r = (e[t] & 128) != 0, a = i.intFromLE(n);
		return this.curve.pointFromY(a, r);
	}, l.prototype.encodeInt = function(e) {
		return e.toArray("le", this.encodingLength);
	}, l.prototype.decodeInt = function(e) {
		return i.intFromLE(e);
	}, l.prototype.isPoint = function(e) {
		return e instanceof this.pointClass;
	};
})), Vs = /* @__PURE__ */ s(((e) => {
	var t = e;
	t.version = (ss(), d(Ko).default).version, t.utils = fs(), t.rand = ps(), t.curve = ys(), t.curves = Ns(), t.ec = Ls(), t.eddsa = Bs();
})), Hs;
(function(e) {
	e[e.ParameterInvalid = 101] = "ParameterInvalid", e[e.ParameterRequired = 102] = "ParameterRequired", e[e.SignMessageFailed = 103] = "SignMessageFailed", e[e.AddressInvalid = 104] = "AddressInvalid", e[e.ReconciliationFailed = 105] = "ReconciliationFailed";
})(Hs ||= {});
var Us = Hs, Ws = class extends Error {
	constructor(e) {
		super(`${e} is required`), this.code = Us.ParameterRequired;
	}
}, Gs = class extends Error {
	constructor() {
		super("Fail to sign the message"), this.code = Us.SignMessageFailed;
	}
}, Ks = class extends Error {
	constructor(e) {
		super(`${e} is an invalid hex string`), this.code = Us.ParameterInvalid;
	}
}, qs = class extends Error {
	constructor(e) {
		super(`Hex string ${e} should start with 0x`), this.code = Us.ParameterInvalid;
	}
}, Js = class extends Error {
	constructor(e, t) {
		super(`'${e}' is not a valid ${t ? `${t} version ` : ""}address payload`), this.code = Us.AddressInvalid, this.type = t;
	}
}, Ys = class extends Error {
	constructor(e, t, n) {
		super(`'${e}' is not a valid ${n ? `${n} version ` : ""}address`), this.code = Us.AddressInvalid, this.type = n, this.stack = t;
	}
}, Xs = class extends Error {
	constructor(e) {
		super(`'${e}' is not a valid code hash`), this.code = Us.AddressInvalid;
	}
}, Zs = class extends Error {
	constructor(e) {
		super(`'${e}' is not a valid hash type`), this.code = Us.AddressInvalid;
	}
}, Qs = class extends Error {
	constructor(e) {
		super(`0x${e.toString(16).padStart(2, "0")} is not a valid address format type`), this.code = Us.AddressInvalid;
	}
}, $s = class extends Error {
	constructor(e, t = "unknown") {
		super(`Address format type 0x${e.toString(16).padStart(2, "0")} doesn't match encode method ${t}`), this.code = Us.AddressInvalid;
	}
}, ec = class extends Error {
	constructor(e, t) {
		super(`Expect outlen to be at least ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, tc = class extends Error {
	constructor(e, t) {
		super(`Expect outlen to be at most ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, nc = class extends Error {
	constructor(e, t) {
		super(`Expect key length to be at least ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, rc = class extends Error {
	constructor(e, t) {
		super(`Expect key length to be at most ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, ic = class extends TypeError {
	constructor() {
		super("Expect out to be \"binary\", \"hex\", Uint8Array, or Buffer"), this.code = Us.ParameterInvalid;
	}
}, ac = class extends TypeError {
	constructor() {
		super("Expect salt to be Uint8Array or Buffer"), this.code = Us.ParameterInvalid;
	}
}, oc = class extends Error {
	constructor(e, t) {
		super(`Expect salt length to be ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, sc = class extends TypeError {
	constructor() {
		super("Expect input to be Uint8Array or Buffer"), this.code = Us.ParameterInvalid;
	}
}, cc = class extends TypeError {
	constructor() {
		super("Expect key to be Uint8Array or Buffer"), this.code = Us.ParameterInvalid;
	}
}, lc = class extends TypeError {
	constructor() {
		super("Expect PERSONAL to be Uint8Array or Buffer"), this.code = Us.ParameterInvalid;
	}
}, uc = class extends Error {
	constructor(e, t) {
		super(`Expect PERSONAL length to be ${t}, but ${e} received`), this.code = Us.ParameterInvalid;
	}
}, dc = class extends Error {
	constructor() {
		super("Private key has invalid length"), this.code = Us.ParameterInvalid;
	}
}, fc = class extends Error {
	constructor() {
		super("Fail to reconcile transaction, try to increase extra count or check the transaction"), this.code = Us.ReconciliationFailed;
	}
}, pc = (e) => {
	if (typeof e != "string" || !e.startsWith("0x") || Number.isNaN(+e)) throw new Ks(e);
	return !0;
}, mc = (e) => {
	if (typeof e == "bigint") return !0;
	if (typeof e == "string") {
		if (!e.startsWith("0x")) throw new qs(e);
		return !0;
	}
	throw TypeError(`${e} should be type of string or bigint`);
}, hc = (e) => {
	mc(e);
	let t = /* @__PURE__ */ new DataView(/* @__PURE__ */ new ArrayBuffer(2));
	return t.setUint16(0, Number(e), !0), `0x${t.getUint16(0, !1).toString(16).padStart(4, "0")}`;
}, gc = (e) => {
	mc(e);
	let t = /* @__PURE__ */ new DataView(/* @__PURE__ */ new ArrayBuffer(4));
	return t.setUint32(0, Number(e), !0), `0x${t.getUint32(0, !1).toString(16).padStart(8, "0")}`;
}, _c = (e) => {
	mc(e);
	let t = (typeof e == "bigint" ? e.toString(16) : e.slice(2)).padStart(16, "0"), n = gc(`0x${t.slice(0, 8)}`).slice(2);
	return `0x${gc(`0x${t.slice(8)}`).slice(2)}${n}`;
}, vc = (e) => {
	if (e === "") return new Uint8Array();
	if (typeof e == "string" && !e.startsWith("0x")) throw new qs(e);
	let t = e.toString(16).replace(/^0x/i, "");
	t = t.length % 2 ? `0${t}` : t;
	let n = [];
	for (let e = 0; e < t.length; e += 2) n.push(parseInt(t.substr(e, 2), 16));
	return new Uint8Array(n);
}, yc = (e) => (pc(e), `0x${vc(e).reduceRight((e, t) => e + t.toString(16).padStart(2, "0"), "")}`), bc = (e) => `0x${[...e].map((e) => e.toString(16).padStart(2, "0")).join("")}`, xc = new (/* @__PURE__ */ u(Vs())).default.ec("secp256k1"), Sc = class {
	constructor(e, { compressed: t = !0 } = { compressed: !0 }) {
		if (this.compressed = !1, this.getPrivateKey = (e = "hex") => e === "hex" ? this.privateKey : this.key.getPrivate(e), this.getPublicKey = (e) => e === "hex" ? this.publicKey : this.key.getPublic(this.compressed, e), this.sign = (e) => {
			let t = typeof e == "string" ? vc(e) : e;
			return `0x${this.key.sign(t, { canonical: !0 }).toDER("hex")}`;
		}, this.verify = (e, t) => {
			let n = typeof e == "string" ? vc(e) : e, r = typeof t == "string" ? vc(t) : t;
			return this.key.verify(n, r);
		}, this.signRecoverable = (e) => {
			let t = typeof e == "string" ? vc(e) : e, { r: n, s: r, recoveryParam: i } = this.key.sign(t, { canonical: !0 });
			if (i === null) throw new Gs();
			return `0x${n.toString(16).padStart(64, "0")}${r.toString(16).padStart(64, "0")}0${i}`;
		}, e === void 0) throw new Ws("Private key");
		if (typeof e == "string" && !e.startsWith("0x")) throw new qs(e);
		if (typeof e == "string" && e.length !== 66 || typeof e == "object" && e.byteLength !== 32) throw new dc();
		this.key = xc.keyFromPrivate(typeof e == "string" ? e.replace(/^0x/, "") : e), this.compressed = t;
	}
	get privateKey() {
		return `0x${this.key.getPrivate("hex").padStart(64, "0")}`;
	}
	get publicKey() {
		return `0x${this.key.getPublic(this.compressed, "hex")}`;
	}
}, Cc = /* @__PURE__ */ c({
	ANYONE_CAN_PAY_MAINNET: () => Ec,
	ANYONE_CAN_PAY_TESTNET: () => Dc,
	NERVOS_DAO: () => Oc,
	SECP256K1_BLAKE160: () => wc,
	SECP256K1_MULTISIG: () => Tc,
	SIMPLE_UDT: () => kc
}), wc = {
	codeHash: "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
	hashType: "type",
	depType: "depGroup",
	mainnetOutPoint: {
		txHash: "0x71a7ba8fc96349fea0ed3a5c47992e3b4084b031a42264a018e0072e8172e46c",
		index: "0x0"
	},
	testnetOutPoint: {
		txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
		index: "0x0"
	}
}, Tc = {
	codeHash: "0x5c5069eb0857efc65e1bca0c07df34c31663b3622fd3876c876320fc9634e2a8",
	hashType: "type",
	depType: "depGroup",
	mainnetOutPoint: {
		txHash: "0x71a7ba8fc96349fea0ed3a5c47992e3b4084b031a42264a018e0072e8172e46c",
		index: "0x1"
	},
	testnetOutPoint: {
		txHash: "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
		index: "0x1"
	}
}, Ec = {
	codeHash: "0xd369597ff47f29fbc0d47d2e3775370d1250b85140c670e4718af712983a2354",
	hashType: "type",
	depType: "depGroup",
	mainnetOutPoint: {
		txHash: "0x4153a2014952d7cac45f285ce9a7c5c0c0e1b21f2d378b82ac1433cb11c25c4d",
		index: "0x0"
	}
}, Dc = {
	codeHash: "0x3419a1c09eb2567f6552ee7a8ecffd64155cffe0f1796e6e61ec088d740c1356",
	hashType: "type",
	depType: "depGroup",
	testnetOutPoint: {
		txHash: "0xec26b0f85ed839ece5f11c4c4e837ec359f5adc4420410f6453b1f6b60fb96a6",
		index: "0x0"
	}
}, Oc = {
	codeHash: "0x82d76d1b75fe2fd9a27dfbaa65a039221a380d76c926f378d3f81cf3e7e13f2e",
	hashType: "type",
	depType: "code",
	mainnetOutPoint: {
		txHash: "0xe2fb199810d49a4d8beec56718ba2593b665db9d52299a0f9e6e75416d73ff5c",
		index: "0x2"
	},
	testnetOutPoint: {
		txHash: "0x8f8c79eb6671709633fe6a46de93c0fedc9c1b8a6527a18d3983879542635c9f",
		index: "0x2"
	}
}, kc = {
	codeHash: "0x48dbf59b4c7ee1547238021b4869bceedf4eea6b43772e5d66ef8865b6ae7212",
	hashType: "data",
	depType: "code",
	testnetOutPoint: {
		txHash: "0xc1b2ae129fad7465aaa9acc9785f842ba3e6e8b8051d899defa89f5508a77958",
		index: "0x0"
	}
}, Ac = 1023, jc;
(function(e) {
	e.Mainnet = "ckb", e.Testnet = "ckt";
})(jc ||= {});
var Mc;
(function(e) {
	e.FullVersion = "0x00", e.HashIdx = "0x01", e.DataCodeHash = "0x02", e.TypeCodeHash = "0x04";
})(Mc ||= {});
var Nc;
(function(e) {
	e.Bech32 = "bech32", e.Bech32m = "bech32m";
})(Nc ||= {});
var Pc = (e, t = !0) => nu.encode(t ? jc.Mainnet : jc.Testnet, nu.toWords(e), Ac), Fc = ({ codeHash: e, hashType: t, args: n }) => {
	if (!n.startsWith("0x")) throw new qs(n);
	if (!e.startsWith("0x") || e.length !== 66) throw new Xs(e);
	let r;
	if ((function(e) {
		e.data = "00", e.type = "01", e.data1 = "02", e.data2 = "04";
	})(r ||= {}), !r[t]) throw new Zs(t);
	return vc(`0x00${e.slice(2)}${r[t]}${n.slice(2)}`);
}, Ic = (e, t = !0) => Pc(Fc(e), t), Lc = (e, t = Mc.HashIdx, n, r) => {
	if (typeof e == "string" && !e.startsWith("0x")) throw new qs(e);
	if (![
		Mc.HashIdx,
		Mc.DataCodeHash,
		Mc.TypeCodeHash,
		Mc.FullVersion
	].includes(t)) throw new Qs(+t);
	if ([Mc.DataCodeHash, Mc.TypeCodeHash].includes(t) && console.warn("Address of 'AddressType.DataCodeHash' or 'AddressType.TypeCodeHash' is deprecated, please use address of AddressPrefix.FullVersion"), n ||= t === Mc.HashIdx ? "0x00" : wc.codeHash, t !== Mc.FullVersion) return new Uint8Array([
		...vc(t),
		...vc(n),
		...typeof e == "string" ? vc(e) : e
	]);
	if (!r && n === wc.codeHash && (r = wc.hashType), !n.startsWith("0x") || n.length !== 66) throw new Xs(n);
	if (!r) throw new Ws("hashType");
	return Fc({
		codeHash: n,
		hashType: r,
		args: typeof e == "string" ? e : bc(e)
	});
}, Rc = (e, { prefix: t = jc.Mainnet, type: n = Mc.HashIdx, codeHashOrCodeHashIndex: r = "" } = {}) => tu.encode(t, tu.toWords(Lc(e, n, r)), Ac), zc = ({ args: e, prefix: t, type: n = Mc.DataCodeHash, codeHash: r }) => Rc(e, {
	prefix: t,
	type: n,
	codeHashOrCodeHashIndex: r
}), Bc = (e, t = {}) => Rc(ru(e), t), Vc = (e, t) => {
	let [n, r, ...i] = e;
	if (t !== Nc.Bech32) throw new $s(n, t);
	switch (r) {
		case 0:
		case 1:
			if (i.length !== 20) throw new Js(e, "short");
			break;
		case 2:
			if (i.length === 20 || i.length === 22 || i.length === 24) break;
			throw new Js(e, "short");
		default: throw new Js(e, "short");
	}
}, Hc = (e, t) => {
	let n = e[0], r = e.slice(1);
	switch (n) {
		case +Mc.HashIdx:
			Vc(e, t);
			break;
		case +Mc.DataCodeHash:
		case +Mc.TypeCodeHash:
			if (t !== Nc.Bech32) throw new $s(n, t);
			if (r.length < 32) throw new Js(e, "full");
			break;
		case +Mc.FullVersion: {
			if (t !== Nc.Bech32m) throw new $s(n, t);
			let e = r.slice(0, 32);
			if (e.length < 32) throw new Xs(bc(e));
			let i = parseInt(r[32].toString(), 16);
			if (!Object.values(Mc).map((e) => +e).includes(i)) throw new Zs(`0x${i.toString(16)}`);
			break;
		}
		default: throw new Js(e);
	}
}, Uc = (e, t = "binary") => {
	let n, r = new Uint8Array();
	try {
		let t = tu.decode(e, Ac);
		n = Nc.Bech32, r = new Uint8Array(tu.fromWords(new Uint8Array(t.words)));
	} catch {
		let t = nu.decode(e, Ac);
		n = Nc.Bech32m, r = new Uint8Array(nu.fromWords(new Uint8Array(t.words)));
	}
	try {
		Hc(r, n);
	} catch (t) {
		throw t instanceof $s ? t : new Ys(e, t.stack, t.type);
	}
	return t === "binary" ? r : bc(r);
}, Wc = (e) => {
	let t = Uc(e), n = t[0];
	switch (n) {
		case +Mc.FullVersion: {
			let e = {
				"00": "data",
				"01": "type",
				"02": "data1",
				"04": "data2"
			}, n = bc(t);
			return {
				codeHash: `0x${n.substr(4, 64)}`,
				hashType: e[n.substr(68, 2)],
				args: `0x${n.substr(70)}`
			};
		}
		case +Mc.HashIdx: {
			let n = [
				wc,
				Tc,
				e.startsWith(jc.Mainnet) ? Ec : Dc
			], r = t[1], i = t.slice(2), a = n[r];
			return {
				codeHash: a.codeHash,
				hashType: a.hashType,
				args: bc(i)
			};
		}
		case +Mc.DataCodeHash:
		case +Mc.TypeCodeHash: {
			let e = bc(t.slice(1)), r = n === +Mc.DataCodeHash ? "data" : "type";
			return {
				codeHash: e.substr(0, 66),
				hashType: r,
				args: `0x${e.substr(66)}`
			};
		}
		default: throw new Qs(n);
	}
}, Gc = 16, Kc = 64, qc = 16, Jc = 64, Yc = 16, Xc = 16, Z = new Uint32Array(32), Zc = new Uint32Array(32), Qc = (e, t, n) => {
	let r = e[t] + e[n], i = e[t + 1] + e[n + 1];
	r >= 4294967296 && i++, e[t] = r, e[t + 1] = i;
}, $c = (e, t, n, r) => {
	let i = e[t] + n;
	n < 0 && (i += 4294967296);
	let a = e[t + 1] + r;
	i >= 4294967296 && a++, e[t] = i, e[t + 1] = a;
}, el = (e, t) => e[t] ^ e[t + 1] << 8 ^ e[t + 2] << 16 ^ e[t + 3] << 24, tl = (e, t, n, r, i, a) => {
	let o = Zc[i], s = Zc[i + 1], c = Zc[a], l = Zc[a + 1];
	Qc(Z, e, t), $c(Z, e, o, s);
	let u = Z[r] ^ Z[e], d = Z[r + 1] ^ Z[e + 1];
	Z[r] = d, Z[r + 1] = u, Qc(Z, n, r), u = Z[t] ^ Z[n], d = Z[t + 1] ^ Z[n + 1], Z[t] = u >>> 24 ^ d << 8, Z[t + 1] = d >>> 24 ^ u << 8, Qc(Z, e, t), $c(Z, e, c, l), u = Z[r] ^ Z[e], d = Z[r + 1] ^ Z[e + 1], Z[r] = u >>> 16 ^ d << 16, Z[r + 1] = d >>> 16 ^ u << 16, Qc(Z, n, r), u = Z[t] ^ Z[n], d = Z[t + 1] ^ Z[n + 1], Z[t] = d >>> 31 ^ u << 1, Z[t + 1] = u >>> 31 ^ d << 1;
}, nl = new Uint32Array([
	4089235720,
	1779033703,
	2227873595,
	3144134277,
	4271175723,
	1013904242,
	1595750129,
	2773480762,
	2917565137,
	1359893119,
	725511199,
	2600822924,
	4215389547,
	528734635,
	327033209,
	1541459225
]), rl = new Uint8Array([
	0,
	1,
	2,
	3,
	4,
	5,
	6,
	7,
	8,
	9,
	10,
	11,
	12,
	13,
	14,
	15,
	14,
	10,
	4,
	8,
	9,
	15,
	13,
	6,
	1,
	12,
	0,
	2,
	11,
	7,
	5,
	3,
	11,
	8,
	12,
	0,
	5,
	2,
	15,
	13,
	10,
	14,
	3,
	6,
	7,
	1,
	9,
	4,
	7,
	9,
	3,
	1,
	13,
	12,
	11,
	14,
	2,
	6,
	5,
	10,
	4,
	0,
	15,
	8,
	9,
	0,
	5,
	7,
	2,
	4,
	10,
	15,
	14,
	1,
	11,
	12,
	6,
	8,
	3,
	13,
	2,
	12,
	6,
	10,
	0,
	11,
	8,
	3,
	4,
	13,
	7,
	5,
	15,
	14,
	1,
	9,
	12,
	5,
	1,
	15,
	14,
	13,
	4,
	10,
	0,
	7,
	6,
	3,
	9,
	2,
	8,
	11,
	13,
	11,
	7,
	14,
	12,
	1,
	3,
	9,
	5,
	0,
	15,
	4,
	8,
	6,
	2,
	10,
	6,
	15,
	14,
	9,
	11,
	3,
	0,
	8,
	12,
	2,
	13,
	7,
	1,
	4,
	10,
	5,
	10,
	2,
	8,
	4,
	7,
	6,
	1,
	5,
	15,
	11,
	9,
	14,
	3,
	12,
	13,
	0,
	0,
	1,
	2,
	3,
	4,
	5,
	6,
	7,
	8,
	9,
	10,
	11,
	12,
	13,
	14,
	15,
	14,
	10,
	4,
	8,
	9,
	15,
	13,
	6,
	1,
	12,
	0,
	2,
	11,
	7,
	5,
	3
].map((e) => e * 2)), il = (e, t) => {
	let n = 0;
	for (n = 0; n < 16; n++) Z[n] = e.h[n], Z[n + 16] = nl[n];
	for (Z[24] ^= e.t, Z[25] ^= e.t / 4294967296, t && (Z[28] = ~Z[28], Z[29] = ~Z[29]), n = 0; n < 32; n++) Zc[n] = el(e.b, 4 * n);
	for (n = 0; n < 12; n++) tl(0, 8, 16, 24, rl[n * 16 + 0], rl[n * 16 + 1]), tl(2, 10, 18, 26, rl[n * 16 + 2], rl[n * 16 + 3]), tl(4, 12, 20, 28, rl[n * 16 + 4], rl[n * 16 + 5]), tl(6, 14, 22, 30, rl[n * 16 + 6], rl[n * 16 + 7]), tl(0, 10, 20, 30, rl[n * 16 + 8], rl[n * 16 + 9]), tl(2, 12, 22, 24, rl[n * 16 + 10], rl[n * 16 + 11]), tl(4, 14, 16, 26, rl[n * 16 + 12], rl[n * 16 + 13]), tl(6, 8, 18, 28, rl[n * 16 + 14], rl[n * 16 + 15]);
	for (n = 0; n < 16; n++) e.h[n] = e.h[n] ^ Z[n] ^ Z[n + 16];
}, al = (e, t) => {
	for (let n = 0; n < t.length; n++) e.c === 128 && (e.t += e.c, il(e, !1), e.c = 0), e.b[e.c++] = +t[n];
}, ol = (e, t) => {
	for (e.t += e.c; e.c < 128;) e.b[e.c++] = 0;
	il(e, !0);
	for (let n = 0; n < e.outlen; n++) t[n] = e.h[n >> 2] >> 8 * (n & 3);
	return t;
}, sl = (e) => e < 16 ? `0${e.toString(16)}` : e.toString(16), cl = (e) => {
	let t = "";
	for (let n = 0; n < e.length; n++) t += sl(+e[n]);
	return t;
}, ll = new Uint8Array([
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0
]), ul = class {
	constructor(e, t, n, r) {
		this.update = (e) => {
			if (!(e instanceof Uint8Array)) throw new sc();
			return al(this, e), this;
		}, this.digest = (e) => {
			let t = !e || e === "binary" || e === "hex" ? new Uint8Array(this.outlen) : e;
			if (!(t instanceof Uint8Array)) throw new ic();
			if (t.length < this.outlen) throw Error("out must have at least outlen bytes of space");
			return ol(this, t), e === "hex" ? cl(t) : t;
		}, this.final = this.digest, ll.fill(0), this.b = new Uint8Array(128), this.h = new Uint32Array(16), this.t = 0, this.c = 0, this.outlen = e, ll[0] = e, t && (ll[1] = t.length), ll[2] = 1, ll[3] = 1, n && ll.set(n, 32), r && ll.set(r, 48);
		for (let e = 0; e < 16; e++) this.h[e] = nl[e] ^ el(ll, e * 4);
		t && (al(this, t), this.c = 128);
	}
}, dl = (e, t, n, r, i) => {
	if (i !== !0) {
		if (e < Gc) throw new ec(e, Gc);
		if (e > Kc) throw new tc(e, Kc);
		if (t !== null) {
			if (!(t instanceof Uint8Array)) throw new cc();
			if (t.length < qc) throw new nc(t.length, qc);
			if (t.length > Jc) throw new rc(t.length, Jc);
		}
		if (n !== null) {
			if (!(n instanceof Uint8Array)) throw new ac();
			if (n.length !== Yc) throw new oc(n.length, Yc);
		}
		if (r !== null) {
			if (!(r instanceof Uint8Array)) throw new lc();
			if (r.length !== Xc) throw new uc(r.length, Xc);
		}
	}
	return new ul(e, t, n, r);
}, fl = new Uint8Array([
	99,
	107,
	98,
	45,
	100,
	101,
	102,
	97,
	117,
	108,
	116,
	45,
	104,
	97,
	115,
	104
]), pl = {
	lock: "",
	inputType: "",
	outputType: ""
}, ml = `0x${"0".repeat(130)}`, hl = {
	blake2b: dl,
	blake160: (e, t = "binary") => {
		let n = typeof e == "string" ? vc(e) : e, r = dl(32, null, null, fl);
		return r.update(n), r.digest(t).slice(0, t === "binary" ? 20 : 40);
	},
	bech32: ur.bech32,
	bech32m: ur.bech32m
}, gl = (e) => {
	let t = [4 + 4 * e.length];
	return e.forEach((n, r) => {
		r && t.push(t[t.length - 1] + e[r - 1]);
	}), t;
}, _l = (e) => {
	if (typeof e != "string" && !Array.isArray(e)) throw TypeError("The array to be serialized should by type of string or bytes");
	return bc(typeof e == "string" ? vc(e) : e);
}, vl = (e) => {
	let t = "";
	return e.forEach((e) => {
		t += _l(e).slice(2);
	}), `0x${t}`;
}, yl = (e) => {
	if (typeof e != "string" && !Array.isArray(e)) throw TypeError("The fixed vector to be serialized should be a string or an array of bytes");
	let t = (typeof e == "string" ? [...vc(e)].map((e) => `0x${e.toString(16)}`) : e).map((e) => _l(e).slice(2));
	return `0x${gc(`0x${t.length.toString(16)}`).slice(2)}${t.join("")}`;
}, bl = (e) => {
	if (!Array.isArray(e)) throw TypeError("The dynamic vector to be serialized should be an array of bytes");
	let t = e.map((e) => _l(e).slice(2)), n = t.join(""), r = "";
	return t.length && (r = gl(t.map((e) => e.length / 2)).map((e) => gc(`0x${e.toString(16)}`).slice(2)).join("")), `0x${gc(`0x${(4 + 4 * t.length + n.length / 2).toString(16)}`).slice(2)}${r}${n}`;
}, xl = (e) => {
	let t = [];
	e.forEach((e) => {
		t.push(_l(e).slice(2));
	});
	let n = t.join("");
	return `0x${gc(`0x${(4 + 4 * e.size + n.length / 2).toString(16)}`).slice(2)}${gl(t.map((e) => e.length / 2)).map((e) => gc(`0x${e.toString(16)}`).slice(2)).join("")}${n}`;
}, Sl = (e) => e || "0x", Cl = (e) => _l(e), wl = (e) => {
	if (e === "data") return "0x00";
	if (e === "type") return "0x01";
	if (e === "data1") return "0x02";
	if (e === "data2") return "0x04";
	throw TypeError("Hash type must be either of 'data' or 'type'");
}, Tl = (e) => yl(e), El = (e) => {
	if (!e) throw new Ws("Script");
	let { codeHash: t = "", hashType: n, args: r = "" } = e, i = Cl(t), a = wl(n), o = Tl(r);
	return xl(new Map([
		["codeHash", i],
		["hashType", a],
		["args", o]
	]));
}, Dl = (e) => gc(e), Ol = (e) => e ? vl(new Map([["txHash", e.txHash], ["index", gc(e.index)]])) : "", kl = (e) => {
	if (e === "code") return "0x00";
	if (e === "depGroup") return "0x01";
	throw TypeError("Dep type must be either of 'code' or 'depGroup'");
}, Al = (e) => {
	let t = Ol(e.outPoint), n = kl(e.depType);
	return vl(new Map([["outPoint", t], ["depType", n]]));
}, jl = (e) => yl(e.map((e) => Al(e))), Ml = (e) => yl(e.map((e) => _l(e))), Nl = (e) => {
	let t = Ol(e.previousOutput), n = _c(e.since);
	return vl(new Map([["since", n], ["previousOutput", t]]));
}, Pl = (e) => yl(e.map((e) => Nl(e))), Fl = (e) => {
	let t = _c(e.capacity), n = El(e.lock), r = e.type ? El(e.type) : "";
	return xl(new Map([
		["capacity", t],
		["lock", n],
		["type", r]
	]));
}, Il = (e) => bl(e.map((e) => Fl(e))), Ll = (e) => bl(e.map((e) => yl(e))), Rl = (e) => {
	let [t, n, r] = [
		e.lock,
		e.inputType,
		e.outputType
	].map((e) => Sl(e) === "0x" ? "0x" : yl(e));
	return xl(new Map([
		["lock", t],
		["inputType", n],
		["outputType", r]
	]));
}, zl = (e) => bl(e.map((e) => yl(e))), Bl = (e) => {
	let t = Dl(e.version), n = jl(e.cellDeps), r = Ml(e.headerDeps), i = Pl(e.inputs), a = Il(e.outputs), o = Ll(e.outputsData);
	return xl(new Map([
		["version", t],
		["cellDeps", n],
		["headerDeps", r],
		["inputs", i],
		["outputs", a],
		["outputsData", o]
	]));
}, Vl = (e) => {
	let t = Bl(e), n = zl(e.witnesses || []);
	return xl(new Map([["raw", t], ["witnesses", n]]));
}, Hl = 32, Ul = 1, Wl = (e) => e.args.slice(2).length / 2 + Hl + Ul, Gl = (e) => 8 + Wl(e.lock) + (e.type ? Wl(e.type) : 0), Q = /* @__PURE__ */ u(Go()), Kl = ({ length: e, index: t, number: n }) => (pc(e), pc(t), pc(n), `0x${Q.default.add(Q.default.add(Q.default.add(Q.default.leftShift(Q.default.BigInt(32), Q.default.BigInt(56)), Q.default.leftShift(Q.default.BigInt(e), Q.default.BigInt(40))), Q.default.leftShift(Q.default.BigInt(t), Q.default.BigInt(24))), Q.default.BigInt(n)).toString(16)}`), ql = (e) => ({
	length: `0x${Q.default.bitwiseAnd(Q.default.signedRightShift(Q.default.BigInt(e), Q.default.BigInt(40)), Q.default.BigInt(65535)).toString(16)}`,
	index: `0x${Q.default.bitwiseAnd(Q.default.signedRightShift(Q.default.BigInt(e), Q.default.BigInt(24)), Q.default.BigInt(65535)).toString(16)}`,
	number: `0x${Q.default.bitwiseAnd(Q.default.BigInt(e), Q.default.BigInt(16777215)).toString(16)}`
}), Jl = (e, t) => {
	let n = ql(e), r = ql(t), i = r.number - +n.number;
	r.index * +n.length > n.index * +r.length && (i += 1);
	let a = i <= 180 ? 180 : (Math.floor((i - 1) / 180) + 1) * 180;
	return Kl({
		index: n.index,
		length: n.length,
		number: `0x${(+n.number + a).toString(16)}`
	});
}, Yl = (e) => Vl(Object.assign(Object.assign({}, e), { witnesses: e.witnesses.map((e) => typeof e == "string" ? e : Rl(e)) })).slice(2).length / 2 + 4, Xl = (e, t) => {
	mc(e), mc(t);
	let n = Q.default.BigInt(1e3), r = Q.default.multiply(Q.default.BigInt(`${e}`), Q.default.BigInt(`${t}`)), i = Q.default.divide(r, n);
	return Q.default.lessThan(Q.default.multiply(i, n), r) ? `0x${Q.default.add(i, Q.default.BigInt(1)).toString(16)}` : `0x${i.toString(16)}`;
}, Zl = (e) => {
	let t = Q.default.BigInt(`${e.changeThreshold}`), n = Q.default.BigInt(`${e.feeRate}`), r = e.tx.outputs[e.tx.outputs.length - 1], i = Q.default.BigInt(r.capacity), a = Q.default.BigInt(Xl(`0x${Yl(e.tx).toString(16)}`, `0x${n.toString(16)}`)), o = Q.default.subtract(Q.default.add(a, t), i);
	if (Q.default.LE(o, Q.default.BigInt(0))) return Object.assign(Object.assign({}, e.tx), { outputs: [...e.tx.outputs.slice(0, -1), Object.assign(Object.assign({}, r), { capacity: `0x${Q.default.subtract(i, a).toString(16)}` })] });
	e.cells.sort((e, t) => +Q.default.subtract(Q.default.BigInt(e.capacity), Q.default.BigInt(t.capacity)));
	let s = Q.default.BigInt(44), c = Q.default.divide(Q.default.multiply(s, n), Q.default.BigInt(1e3));
	for (let n = 1; n <= Math.min(e.extraCount, e.cells.length); n++) {
		let i = Q.default.multiply(Q.default.BigInt(n), c), a = Q.default.add(o, i), s = e.cells.slice(0, n).reduce((e, t) => Q.default.add(e, Q.default.BigInt(t.capacity)), Q.default.BigInt(0));
		if (Q.default.GE(s, a)) {
			let i = [...e.tx.inputs, ...e.cells.slice(0, n).map((e) => ({
				previousOutput: e.outPoint,
				since: "0x0"
			}))], o = Q.default.add(t, Q.default.subtract(s, a)), c = Object.assign(Object.assign({}, r), { capacity: `0x${o.toString(16)}` }), l = [...e.tx.outputs.slice(0, -1), c];
			return Object.assign(Object.assign({}, e.tx), {
				inputs: i,
				outputs: l
			});
		}
	}
	throw new fc();
}, Ql = /* @__PURE__ */ c({ extraInputs: () => Zl }), $l = /* @__PURE__ */ c({
	AddressException: () => Ys,
	AddressFormatTypeAndEncodeMethodNotMatchException: () => $s,
	AddressFormatTypeException: () => Qs,
	AddressPayloadException: () => Js,
	AddressPrefix: () => jc,
	AddressType: () => Mc,
	Bech32Type: () => Nc,
	CodeHashException: () => Xs,
	ECPair: () => Sc,
	EMPTY_SECP_SIG: () => ml,
	EMPTY_WITNESS_ARGS: () => pl,
	ErrorCode: () => Hs,
	HashTypeException: () => Zs,
	HexStringException: () => Ks,
	HexStringWithout0xException: () => qs,
	InputTypeException: () => sc,
	JSBI: () => Q.default,
	KeyLenTooLargeException: () => rc,
	KeyLenTooSmallException: () => nc,
	KeyTypeException: () => cc,
	OutLenTooLargeException: () => tc,
	OutLenTooSmallException: () => ec,
	OutTypeException: () => ic,
	PERSONAL: () => fl,
	ParameterRequiredException: () => Ws,
	PersonalLenException: () => uc,
	PersonalTypeException: () => lc,
	PrivateKeyLenException: () => dc,
	ReconciliationException: () => fc,
	SaltLenException: () => oc,
	SaltTypeException: () => ac,
	SignMessageException: () => Gs,
	addressToScript: () => Wc,
	assertToBeHexString: () => pc,
	assertToBeHexStringOrBigint: () => mc,
	bech32: () => tu,
	bech32Address: () => Rc,
	bech32m: () => nu,
	blake160: () => ru,
	blake2b: () => eu,
	bytesToHex: () => bc,
	calculateMaximumWithdraw: () => lu,
	calculateTransactionFee: () => Xl,
	cellOccupied: () => Gl,
	extractDAOData: () => cu,
	fullLengthSize: () => 4,
	fullPayloadToAddress: () => zc,
	getOffsets: () => gl,
	getTransactionSize: () => Yl,
	getWithdrawEpoch: () => Jl,
	hexToBytes: () => vc,
	offsetSize: () => 4,
	parseAddress: () => Uc,
	parseEpoch: () => ql,
	privateKeyToAddress: () => su,
	privateKeyToPublicKey: () => ou,
	pubkeyToAddress: () => Bc,
	rawTransactionToHash: () => au,
	reconcilers: () => Ql,
	scriptOccupied: () => Wl,
	scriptToAddress: () => Ic,
	scriptToHash: () => iu,
	serializeArgs: () => Tl,
	serializeArray: () => _l,
	serializeCellDep: () => Al,
	serializeCellDeps: () => jl,
	serializeCodeHash: () => Cl,
	serializeDepType: () => kl,
	serializeDynVec: () => bl,
	serializeEpoch: () => Kl,
	serializeFixVec: () => yl,
	serializeHashType: () => wl,
	serializeHeaderDeps: () => Ml,
	serializeInput: () => Nl,
	serializeInputs: () => Pl,
	serializeOption: () => Sl,
	serializeOutPoint: () => Ol,
	serializeOutput: () => Fl,
	serializeOutputs: () => Il,
	serializeOutputsData: () => Ll,
	serializeRawTransaction: () => Bl,
	serializeScript: () => El,
	serializeStruct: () => vl,
	serializeTable: () => xl,
	serializeTransaction: () => Vl,
	serializeVersion: () => Dl,
	serializeWitnessArgs: () => Rl,
	serializeWitnesses: () => zl,
	systemScripts: () => Cc,
	toAddressPayload: () => Lc,
	toBigEndian: () => yc,
	toUint16Le: () => hc,
	toUint32Le: () => gc,
	toUint64Le: () => _c
}), { blake2b: eu, bech32: tu, bech32m: nu, blake160: ru } = hl, iu = (e) => {
	if (!e) throw new Ws("Script");
	let t = El(e), n = eu(32, null, null, fl);
	return n.update(vc(t)), `0x${n.digest("hex")}`;
}, au = (e) => {
	if (!e) throw new Ws("Raw transaction");
	let t = Bl(e), n = eu(32, null, null, fl);
	return n.update(vc(t)), `0x${n.digest("hex")}`;
}, ou = (e) => new Sc(e).publicKey, su = (e, t) => Bc(ou(e), t), cu = (e) => {
	if (!e.startsWith("0x")) throw new qs(e);
	let t = e.replace("0x", "");
	return {
		c: yc(`0x${t.slice(0, 16)}`),
		ar: yc(`0x${t.slice(16, 32)}`),
		s: yc(`0x${t.slice(32, 48)}`),
		u: yc(`0x${t.slice(48, 64)}`)
	};
}, lu = (e, t, n, r) => {
	let i = Gl(e) + t.slice(2).length / 2, a = Q.default.asUintN(128, Q.default.multiply(Q.default.BigInt(1e8), Q.default.BigInt(i)));
	return `0x${Q.default.add(Q.default.divide(Q.default.multiply(Q.default.subtract(Q.default.asUintN(128, Q.default.BigInt(e.capacity)), a), Q.default.asUintN(128, Q.default.BigInt(cu(r).ar))), Q.default.asUintN(128, Q.default.BigInt(cu(n).ar))), a).toString(16)}`;
}, uu = /* @__PURE__ */ s(((e, t) => {
	var n = typeof globalThis < "u" && globalThis || typeof self < "u" && self || typeof global < "u" && global, r = (function() {
		function e() {
			this.fetch = !1, this.DOMException = n.DOMException;
		}
		return e.prototype = n, new e();
	})();
	(function(e) {
		(function(t) {
			var n = e !== void 0 && e || typeof self < "u" && self || n !== void 0 && n, r = {
				searchParams: "URLSearchParams" in n,
				iterable: "Symbol" in n && "iterator" in Symbol,
				blob: "FileReader" in n && "Blob" in n && (function() {
					try {
						return new Blob(), !0;
					} catch {
						return !1;
					}
				})(),
				formData: "FormData" in n,
				arrayBuffer: "ArrayBuffer" in n
			};
			function i(e) {
				return e && DataView.prototype.isPrototypeOf(e);
			}
			if (r.arrayBuffer) var a = [
				"[object Int8Array]",
				"[object Uint8Array]",
				"[object Uint8ClampedArray]",
				"[object Int16Array]",
				"[object Uint16Array]",
				"[object Int32Array]",
				"[object Uint32Array]",
				"[object Float32Array]",
				"[object Float64Array]"
			], o = ArrayBuffer.isView || function(e) {
				return e && a.indexOf(Object.prototype.toString.call(e)) > -1;
			};
			function s(e) {
				if (typeof e != "string" && (e = String(e)), /[^a-z0-9\-#$%&'*+.^_`|~!]/i.test(e) || e === "") throw TypeError("Invalid character in header field name: \"" + e + "\"");
				return e.toLowerCase();
			}
			function c(e) {
				return typeof e != "string" && (e = String(e)), e;
			}
			function l(e) {
				var t = { next: function() {
					var t = e.shift();
					return {
						done: t === void 0,
						value: t
					};
				} };
				return r.iterable && (t[Symbol.iterator] = function() {
					return t;
				}), t;
			}
			function u(e) {
				this.map = {}, e instanceof u ? e.forEach(function(e, t) {
					this.append(t, e);
				}, this) : Array.isArray(e) ? e.forEach(function(e) {
					this.append(e[0], e[1]);
				}, this) : e && Object.getOwnPropertyNames(e).forEach(function(t) {
					this.append(t, e[t]);
				}, this);
			}
			u.prototype.append = function(e, t) {
				e = s(e), t = c(t);
				var n = this.map[e];
				this.map[e] = n ? n + ", " + t : t;
			}, u.prototype.delete = function(e) {
				delete this.map[s(e)];
			}, u.prototype.get = function(e) {
				return e = s(e), this.has(e) ? this.map[e] : null;
			}, u.prototype.has = function(e) {
				return this.map.hasOwnProperty(s(e));
			}, u.prototype.set = function(e, t) {
				this.map[s(e)] = c(t);
			}, u.prototype.forEach = function(e, t) {
				for (var n in this.map) this.map.hasOwnProperty(n) && e.call(t, this.map[n], n, this);
			}, u.prototype.keys = function() {
				var e = [];
				return this.forEach(function(t, n) {
					e.push(n);
				}), l(e);
			}, u.prototype.values = function() {
				var e = [];
				return this.forEach(function(t) {
					e.push(t);
				}), l(e);
			}, u.prototype.entries = function() {
				var e = [];
				return this.forEach(function(t, n) {
					e.push([n, t]);
				}), l(e);
			}, r.iterable && (u.prototype[Symbol.iterator] = u.prototype.entries);
			function d(e) {
				if (e.bodyUsed) return Promise.reject(/* @__PURE__ */ TypeError("Already read"));
				e.bodyUsed = !0;
			}
			function f(e) {
				return new Promise(function(t, n) {
					e.onload = function() {
						t(e.result);
					}, e.onerror = function() {
						n(e.error);
					};
				});
			}
			function p(e) {
				var t = new FileReader(), n = f(t);
				return t.readAsArrayBuffer(e), n;
			}
			function m(e) {
				var t = new FileReader(), n = f(t);
				return t.readAsText(e), n;
			}
			function h(e) {
				for (var t = new Uint8Array(e), n = Array(t.length), r = 0; r < t.length; r++) n[r] = String.fromCharCode(t[r]);
				return n.join("");
			}
			function g(e) {
				if (e.slice) return e.slice(0);
				var t = new Uint8Array(e.byteLength);
				return t.set(new Uint8Array(e)), t.buffer;
			}
			function _() {
				return this.bodyUsed = !1, this._initBody = function(e) {
					this.bodyUsed = this.bodyUsed, this._bodyInit = e, e ? typeof e == "string" ? this._bodyText = e : r.blob && Blob.prototype.isPrototypeOf(e) ? this._bodyBlob = e : r.formData && FormData.prototype.isPrototypeOf(e) ? this._bodyFormData = e : r.searchParams && URLSearchParams.prototype.isPrototypeOf(e) ? this._bodyText = e.toString() : r.arrayBuffer && r.blob && i(e) ? (this._bodyArrayBuffer = g(e.buffer), this._bodyInit = new Blob([this._bodyArrayBuffer])) : r.arrayBuffer && (ArrayBuffer.prototype.isPrototypeOf(e) || o(e)) ? this._bodyArrayBuffer = g(e) : this._bodyText = e = Object.prototype.toString.call(e) : this._bodyText = "", this.headers.get("content-type") || (typeof e == "string" ? this.headers.set("content-type", "text/plain;charset=UTF-8") : this._bodyBlob && this._bodyBlob.type ? this.headers.set("content-type", this._bodyBlob.type) : r.searchParams && URLSearchParams.prototype.isPrototypeOf(e) && this.headers.set("content-type", "application/x-www-form-urlencoded;charset=UTF-8"));
				}, r.blob && (this.blob = function() {
					var e = d(this);
					if (e) return e;
					if (this._bodyBlob) return Promise.resolve(this._bodyBlob);
					if (this._bodyArrayBuffer) return Promise.resolve(new Blob([this._bodyArrayBuffer]));
					if (this._bodyFormData) throw Error("could not read FormData body as blob");
					return Promise.resolve(new Blob([this._bodyText]));
				}, this.arrayBuffer = function() {
					return this._bodyArrayBuffer ? d(this) || (ArrayBuffer.isView(this._bodyArrayBuffer) ? Promise.resolve(this._bodyArrayBuffer.buffer.slice(this._bodyArrayBuffer.byteOffset, this._bodyArrayBuffer.byteOffset + this._bodyArrayBuffer.byteLength)) : Promise.resolve(this._bodyArrayBuffer)) : this.blob().then(p);
				}), this.text = function() {
					var e = d(this);
					if (e) return e;
					if (this._bodyBlob) return m(this._bodyBlob);
					if (this._bodyArrayBuffer) return Promise.resolve(h(this._bodyArrayBuffer));
					if (this._bodyFormData) throw Error("could not read FormData body as text");
					return Promise.resolve(this._bodyText);
				}, r.formData && (this.formData = function() {
					return this.text().then(x);
				}), this.json = function() {
					return this.text().then(JSON.parse);
				}, this;
			}
			var v = [
				"DELETE",
				"GET",
				"HEAD",
				"OPTIONS",
				"POST",
				"PUT"
			];
			function y(e) {
				var t = e.toUpperCase();
				return v.indexOf(t) > -1 ? t : e;
			}
			function b(e, t) {
				if (!(this instanceof b)) throw TypeError("Please use the \"new\" operator, this DOM object constructor cannot be called as a function.");
				t ||= {};
				var n = t.body;
				if (e instanceof b) {
					if (e.bodyUsed) throw TypeError("Already read");
					this.url = e.url, this.credentials = e.credentials, t.headers || (this.headers = new u(e.headers)), this.method = e.method, this.mode = e.mode, this.signal = e.signal, !n && e._bodyInit != null && (n = e._bodyInit, e.bodyUsed = !0);
				} else this.url = String(e);
				if (this.credentials = t.credentials || this.credentials || "same-origin", (t.headers || !this.headers) && (this.headers = new u(t.headers)), this.method = y(t.method || this.method || "GET"), this.mode = t.mode || this.mode || null, this.signal = t.signal || this.signal, this.referrer = null, (this.method === "GET" || this.method === "HEAD") && n) throw TypeError("Body not allowed for GET or HEAD requests");
				if (this._initBody(n), (this.method === "GET" || this.method === "HEAD") && (t.cache === "no-store" || t.cache === "no-cache")) {
					var r = /([?&])_=[^&]*/;
					r.test(this.url) ? this.url = this.url.replace(r, "$1_=" + (/* @__PURE__ */ new Date()).getTime()) : this.url += (/\?/.test(this.url) ? "&" : "?") + "_=" + (/* @__PURE__ */ new Date()).getTime();
				}
			}
			b.prototype.clone = function() {
				return new b(this, { body: this._bodyInit });
			};
			function x(e) {
				var t = new FormData();
				return e.trim().split("&").forEach(function(e) {
					if (e) {
						var n = e.split("="), r = n.shift().replace(/\+/g, " "), i = n.join("=").replace(/\+/g, " ");
						t.append(decodeURIComponent(r), decodeURIComponent(i));
					}
				}), t;
			}
			function S(e) {
				var t = new u();
				return e.replace(/\r?\n[\t ]+/g, " ").split("\r").map(function(e) {
					return e.indexOf("\n") === 0 ? e.substr(1, e.length) : e;
				}).forEach(function(e) {
					var n = e.split(":"), r = n.shift().trim();
					if (r) {
						var i = n.join(":").trim();
						t.append(r, i);
					}
				}), t;
			}
			_.call(b.prototype);
			function C(e, t) {
				if (!(this instanceof C)) throw TypeError("Please use the \"new\" operator, this DOM object constructor cannot be called as a function.");
				t ||= {}, this.type = "default", this.status = t.status === void 0 ? 200 : t.status, this.ok = this.status >= 200 && this.status < 300, this.statusText = t.statusText === void 0 ? "" : "" + t.statusText, this.headers = new u(t.headers), this.url = t.url || "", this._initBody(e);
			}
			_.call(C.prototype), C.prototype.clone = function() {
				return new C(this._bodyInit, {
					status: this.status,
					statusText: this.statusText,
					headers: new u(this.headers),
					url: this.url
				});
			}, C.error = function() {
				var e = new C(null, {
					status: 0,
					statusText: ""
				});
				return e.type = "error", e;
			};
			var w = [
				301,
				302,
				303,
				307,
				308
			];
			C.redirect = function(e, t) {
				if (w.indexOf(t) === -1) throw RangeError("Invalid status code");
				return new C(null, {
					status: t,
					headers: { location: e }
				});
			}, t.DOMException = n.DOMException;
			try {
				new t.DOMException();
			} catch {
				t.DOMException = function(e, t) {
					this.message = e, this.name = t, this.stack = Error(e).stack;
				}, t.DOMException.prototype = Object.create(Error.prototype), t.DOMException.prototype.constructor = t.DOMException;
			}
			function T(e, i) {
				return new Promise(function(a, o) {
					var s = new b(e, i);
					if (s.signal && s.signal.aborted) return o(new t.DOMException("Aborted", "AbortError"));
					var l = new XMLHttpRequest();
					function d() {
						l.abort();
					}
					l.onload = function() {
						var e = {
							status: l.status,
							statusText: l.statusText,
							headers: S(l.getAllResponseHeaders() || "")
						};
						e.url = "responseURL" in l ? l.responseURL : e.headers.get("X-Request-URL");
						var t = "response" in l ? l.response : l.responseText;
						setTimeout(function() {
							a(new C(t, e));
						}, 0);
					}, l.onerror = function() {
						setTimeout(function() {
							o(/* @__PURE__ */ TypeError("Network request failed"));
						}, 0);
					}, l.ontimeout = function() {
						setTimeout(function() {
							o(/* @__PURE__ */ TypeError("Network request failed"));
						}, 0);
					}, l.onabort = function() {
						setTimeout(function() {
							o(new t.DOMException("Aborted", "AbortError"));
						}, 0);
					};
					function f(e) {
						try {
							return e === "" && n.location.href ? n.location.href : e;
						} catch {
							return e;
						}
					}
					l.open(s.method, f(s.url), !0), s.credentials === "include" ? l.withCredentials = !0 : s.credentials === "omit" && (l.withCredentials = !1), "responseType" in l && (r.blob ? l.responseType = "blob" : r.arrayBuffer && s.headers.get("Content-Type") && s.headers.get("Content-Type").indexOf("application/octet-stream") !== -1 && (l.responseType = "arraybuffer")), i && typeof i.headers == "object" && !(i.headers instanceof u) ? Object.getOwnPropertyNames(i.headers).forEach(function(e) {
						l.setRequestHeader(e, c(i.headers[e]));
					}) : s.headers.forEach(function(e, t) {
						l.setRequestHeader(t, e);
					}), s.signal && (s.signal.addEventListener("abort", d), l.onreadystatechange = function() {
						l.readyState === 4 && s.signal.removeEventListener("abort", d);
					}), l.send(s._bodyInit === void 0 ? null : s._bodyInit);
				});
			}
			return T.polyfill = !0, n.fetch || (n.fetch = T, n.Headers = u, n.Request = b, n.Response = C), t.Headers = u, t.Request = b, t.Response = C, t.fetch = T, t;
		})({});
	})(r), r.fetch.ponyfill = !0, delete r.fetch.polyfill;
	var i = n.fetch ? n : r;
	e = i.fetch, e.default = i.fetch, e.fetch = i.fetch, e.Headers = i.Headers, e.Request = i.Request, e.Response = i.Response, t.exports = e;
})), du = globalThis.crypto.subtle, fu = /* @__PURE__ */ u(uu(), 1), pu = () => Date.now(), mu = class {
	constructor(e) {
		this.url = e;
	}
	async baseRPC(e, t, n = this.url) {
		let r = {
			id: pu(),
			jsonrpc: "2.0",
			method: e,
			params: t ?? null
		}, i = JSON.stringify(r, null, ""), a = await (0, fu.default)(n, {
			method: "post",
			headers: { "Content-Type": "application/json" },
			body: i
		}).then(async (e) => e.json());
		if (a.error != null) throw Error(`RPC error: ${JSON.stringify(a.error)}`);
		return a.result;
	}
	async generateSubkeyUnlockSmt(e) {
		return await this.baseRPC("generate_subkey_unlock_smt", e);
	}
};
function hu(e) {
	let t = Array.from(new Uint8Array(e), (e) => `00${e.toString(16)}`.slice(-2)).join(""), n = Number.parseInt(t.substr(6, 2), 16) * 2, r = t.substr(8, n), i = t.substr(12 + n);
	r = r.length > 64 ? r.substr(-64) : r.padStart(64, "0"), i = i.length > 64 ? i.substr(-64) : i.padStart(64, "0");
	let a = `${r}${i}`;
	return new Uint8Array(a.match(/[\da-f]{2}/gi).map((e) => Number.parseInt(e, 16)));
}
var gu = (e, t) => {
	try {
		let n = wo(xo(t));
		return JSON.parse(n).challenge === yo(Co(e));
	} catch {
		return !1;
	}
}, _u = async (e, t, n) => {
	try {
		let r = "RSASSA-PKCS1-v1_5", i = bo(n), a = vo(e), o = vo(t), s = new Uint8Array(i.slice(0, 3)).reverse(), c = new Uint8Array(i.slice(4)).reverse(), l = {
			alg: "RS256",
			ext: !0,
			key_ops: ["verify"],
			kty: "RSA",
			e: yo(s),
			n: yo(c)
		}, u = await du.importKey("jwk", l, {
			name: r,
			hash: "SHA-256"
		}, !1, ["verify"]);
		return await du.verify(r, u, o, a);
	} catch (e) {
		return console.error(e), !1;
	}
}, vu = async ({ message: e, signature: t, pubkey: n, challenge: r, alg: i }) => {
	try {
		let a = bo(`${n}`), o = vo(e), s = vo(t), c = o.slice(0, 37), l = o.slice(37);
		if (!gu(r, l)) return !1;
		let u = So(c, await du.digest("SHA-256", l)), d = i === Eo.ES256, f = d ? {
			kty: "EC",
			crv: "P-256",
			x: yo(a.slice(0, 32)),
			y: yo(a.slice(32))
		} : {
			alg: "RS256",
			ext: !0,
			key_ops: ["verify"],
			kty: "RSA",
			e: yo(new Uint8Array(a.slice(0, 3)).reverse()),
			n: yo(new Uint8Array(a.slice(4)).reverse())
		}, p = d ? {
			name: "ECDSA",
			namedCurve: "P-256",
			hash: { name: "SHA-256" }
		} : {
			name: "RSASSA-PKCS1-v1_5",
			hash: "SHA-256"
		}, m = await du.importKey("jwk", f, p, !1, ["verify"]);
		return await du.verify(p, m, i === Eo.RS256 ? s : hu(s), u);
	} catch (e) {
		return console.error(e), !1;
	}
}, yu = async (e) => {
	let { message: t, signature: n, pubkey: r, keyType: i } = e;
	return i === "main_key" || i === "sub_key" ? vu(e) : _u(t, n, r);
}, { PERSONAL: bu, addressToScript: xu, blake160: Su, blake2b: Cu, hexToBytes: wu, toUint64Le: Tu, serializeScript: Eu, rawTransactionToHash: Du, serializeWitnessArgs: Ou } = $l;
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/ckb/verifyJoyId.js
function ku(e, t, n) {
	let r = typeof e == "string" ? e : K(e).slice(2), { publicKey: i, keyType: a } = JSON.parse(n);
	return yu({
		challenge: r,
		pubkey: i,
		keyType: a,
		...JSON.parse(t)
	});
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/doge/verify.js
function Au(e, t) {
	return co(e, t ?? "Dogecoin Signed Message:\n");
}
function ju(e, t, n) {
	let r = typeof e == "string" ? e : K(e).slice(2), i = y(t, "base64"), a = i[0], o = i.slice(1), s = Ca.Signature.fromCompact(K(o).slice(2)).addRecoveryBit(a - 31);
	return uo(n) === K(lo(s.recoverPublicKey(Au(r)).toHex()));
}
//#endregion
//#region node_modules/ethers/lib.esm/_version.js
var Mu = "6.16.0";
//#endregion
//#region node_modules/ethers/lib.esm/utils/properties.js
function Nu(e, t, n) {
	let r = t.split("|").map((e) => e.trim());
	for (let n = 0; n < r.length; n++) switch (t) {
		case "any": return;
		case "bigint":
		case "boolean":
		case "number":
		case "string": if (typeof e === t) return;
	}
	let i = /* @__PURE__ */ Error(`invalid value for type ${t}`);
	throw i.code = "INVALID_ARGUMENT", i.argument = `value.${n}`, i.value = e, i;
}
function Pu(e, t, n) {
	for (let r in t) {
		let i = t[r], a = n ? n[r] : null;
		a && Nu(i, a, r), Object.defineProperty(e, r, {
			enumerable: !0,
			value: i,
			writable: !1
		});
	}
}
//#endregion
//#region node_modules/ethers/lib.esm/utils/errors.js
function Fu(e, t) {
	if (e == null) return "null";
	if (t ??= /* @__PURE__ */ new Set(), typeof e == "object") {
		if (t.has(e)) return "[Circular]";
		t.add(e);
	}
	if (Array.isArray(e)) return "[ " + e.map((e) => Fu(e, t)).join(", ") + " ]";
	if (e instanceof Uint8Array) {
		let t = "0123456789abcdef", n = "0x";
		for (let r = 0; r < e.length; r++) n += t[e[r] >> 4], n += t[e[r] & 15];
		return n;
	}
	if (typeof e == "object" && typeof e.toJSON == "function") return Fu(e.toJSON(), t);
	switch (typeof e) {
		case "boolean":
		case "number":
		case "symbol": return e.toString();
		case "bigint": return BigInt(e).toString();
		case "string": return JSON.stringify(e);
		case "object": {
			let n = Object.keys(e);
			return n.sort(), "{ " + n.map((n) => `${Fu(n, t)}: ${Fu(e[n], t)}`).join(", ") + " }";
		}
	}
	return "[ COULD NOT SERIALIZE ]";
}
function Iu(e, t, n) {
	let r = e;
	{
		let r = [];
		if (n) {
			if ("message" in n || "code" in n || "name" in n) throw Error(`value will overwrite populated values: ${Fu(n)}`);
			for (let e in n) {
				if (e === "shortMessage") continue;
				let t = n[e];
				r.push(e + "=" + Fu(t));
			}
		}
		r.push(`code=${t}`), r.push(`version=${Mu}`), r.length && (e += " (" + r.join(", ") + ")");
	}
	let i;
	switch (t) {
		case "INVALID_ARGUMENT":
			i = TypeError(e);
			break;
		case "NUMERIC_FAULT":
		case "BUFFER_OVERRUN":
			i = RangeError(e);
			break;
		default: i = Error(e);
	}
	return Pu(i, { code: t }), n && Object.assign(i, n), i.shortMessage ?? Pu(i, { shortMessage: r }), i;
}
function Lu(e, t, n, r) {
	if (!e) throw Iu(t, n, r);
}
function $(e, t, n, r) {
	Lu(e, t, "INVALID_ARGUMENT", {
		argument: n,
		value: r
	});
}
var Ru = [
	"NFD",
	"NFC",
	"NFKD",
	"NFKC"
].reduce((e, t) => {
	try {
		/* c8 ignore start */
		if ("test".normalize(t) !== "test") throw Error("bad");
		/* c8 ignore stop */
		if (t === "NFD" && "é".normalize("NFD") !== "é") throw Error("broken");
		e.push(t);
	} catch {}
	return e;
}, []);
function zu(e) {
	Lu(Ru.indexOf(e) >= 0, "platform missing String.prototype.normalize", "UNSUPPORTED_OPERATION", {
		operation: "String.prototype.normalize",
		info: { form: e }
	});
}
function Bu(e, t, n) {
	if (n ??= "", e !== t) {
		let e = n, t = "new";
		n && (e += ".", t += " " + n), Lu(!1, `private constructor; use ${e}from* methods`, "UNSUPPORTED_OPERATION", { operation: t });
	}
}
//#endregion
//#region node_modules/ethers/lib.esm/utils/data.js
function Vu(e, t, n) {
	if (e instanceof Uint8Array) return n ? new Uint8Array(e) : e;
	if (typeof e == "string" && e.length % 2 == 0 && e.match(/^0x[0-9a-f]*$/i)) {
		let t = new Uint8Array((e.length - 2) / 2), n = 2;
		for (let r = 0; r < t.length; r++) t[r] = parseInt(e.substring(n, n + 2), 16), n += 2;
		return t;
	}
	$(!1, "invalid BytesLike value", t || "value", e);
}
function Hu(e, t) {
	return Vu(e, t, !1);
}
function Uu(e, t) {
	return Vu(e, t, !0);
}
function Wu(e, t) {
	return !(typeof e != "string" || !e.match(/^0x[0-9A-Fa-f]*$/) || typeof t == "number" && e.length !== 2 + 2 * t || t === !0 && e.length % 2 != 0);
}
var Gu = "0123456789abcdef";
function Ku(e) {
	let t = Hu(e), n = "0x";
	for (let e = 0; e < t.length; e++) {
		let r = t[e];
		n += Gu[(r & 240) >> 4] + Gu[r & 15];
	}
	return n;
}
function qu(e) {
	return "0x" + e.map((e) => Ku(e).substring(2)).join("");
}
function Ju(e) {
	return Wu(e, !0) ? (e.length - 2) / 2 : Hu(e).length;
}
function Yu(e, t, n) {
	let r = Hu(e);
	Lu(t >= r.length, "padding exceeds data length", "BUFFER_OVERRUN", {
		buffer: new Uint8Array(r),
		length: t,
		offset: t + 1
	});
	let i = new Uint8Array(t);
	return i.fill(0), n ? i.set(r, t - r.length) : i.set(r, 0), Ku(i);
}
function Xu(e, t) {
	return Yu(e, t, !0);
}
//#endregion
//#region node_modules/ethers/lib.esm/utils/maths.js
var Zu = BigInt(0), Qu = 9007199254740991;
function $u(e, t) {
	switch (typeof e) {
		case "bigint": return e;
		case "number": return $(Number.isInteger(e), "underflow", t || "value", e), $(e >= -Qu && e <= Qu, "overflow", t || "value", e), BigInt(e);
		case "string": try {
			if (e === "") throw Error("empty string");
			return e[0] === "-" && e[1] !== "-" ? -BigInt(e.substring(1)) : BigInt(e);
		} catch (n) {
			$(!1, `invalid BigNumberish string: ${n.message}`, t || "value", e);
		}
	}
	$(!1, "invalid BigNumberish value", t || "value", e);
}
function ed(e, t) {
	let n = $u(e, t);
	return Lu(n >= Zu, "unsigned value cannot be negative", "NUMERIC_FAULT", {
		fault: "overflow",
		operation: "getUint",
		value: e
	}), n;
}
function td(e, t) {
	switch (typeof e) {
		case "bigint": return $(e >= -Qu && e <= Qu, "overflow", t || "value", e), Number(e);
		case "number": return $(Number.isInteger(e), "underflow", t || "value", e), $(e >= -Qu && e <= Qu, "overflow", t || "value", e), e;
		case "string": try {
			if (e === "") throw Error("empty string");
			return td(BigInt(e), t);
		} catch (n) {
			$(!1, `invalid numeric string: ${n.message}`, t || "value", e);
		}
	}
	$(!1, "invalid numeric value", t || "value", e);
}
function nd(e, t) {
	let n = ed(e, "value"), r = n.toString(16);
	if (t == null) r.length % 2 && (r = "0" + r);
	else {
		let i = td(t, "width");
		if (i === 0 && n === Zu) return "0x";
		for (Lu(i * 2 >= r.length, `value exceeds width (${i} bytes)`, "NUMERIC_FAULT", {
			operation: "toBeHex",
			fault: "overflow",
			value: e
		}); r.length < i * 2;) r = "0" + r;
	}
	return "0x" + r;
}
function rd(e, t) {
	let n = ed(e, "value");
	if (n === Zu) {
		let e = t == null ? 0 : td(t, "width");
		return new Uint8Array(e);
	}
	let r = n.toString(16);
	if (r.length % 2 && (r = "0" + r), t != null) {
		let n = td(t, "width");
		for (; r.length < n * 2;) r = "00" + r;
		Lu(n * 2 === r.length, `value exceeds width (${n} bytes)`, "NUMERIC_FAULT", {
			operation: "toBeArray",
			fault: "overflow",
			value: e
		});
	}
	let i = new Uint8Array(r.length / 2);
	for (let e = 0; e < i.length; e++) {
		let t = e * 2;
		i[e] = parseInt(r.substring(t, t + 2), 16);
	}
	return i;
}
//#endregion
//#region node_modules/ethers/lib.esm/utils/utf8.js
function id(e, t, n, r, i) {
	$(!1, `invalid codepoint at offset ${t}; ${e}`, "bytes", n);
}
function ad(e, t, n, r, i) {
	if (e === "BAD_PREFIX" || e === "UNEXPECTED_CONTINUE") {
		let e = 0;
		for (let r = t + 1; r < n.length && n[r] >> 6 == 2; r++) e++;
		return e;
	}
	return e === "OVERRUN" ? n.length - t - 1 : 0;
}
function od(e, t, n, r, i) {
	return e === "OVERLONG" ? ($(typeof i == "number", "invalid bad code point for replacement", "badCodepoint", i), r.push(i), 0) : (r.push(65533), ad(e, t, n, r, i));
}
Object.freeze({
	error: id,
	ignore: ad,
	replace: od
});
function sd(e, t) {
	$(typeof e == "string", "invalid string value", "str", e), t != null && (zu(t), e = e.normalize(t));
	let n = [];
	for (let t = 0; t < e.length; t++) {
		let r = e.charCodeAt(t);
		if (r < 128) n.push(r);
		else if (r < 2048) n.push(r >> 6 | 192), n.push(r & 63 | 128);
		else if ((r & 64512) == 55296) {
			t++;
			let i = e.charCodeAt(t);
			$(t < e.length && (i & 64512) == 56320, "invalid surrogate pair", "str", e);
			let a = 65536 + ((r & 1023) << 10) + (i & 1023);
			n.push(a >> 18 | 240), n.push(a >> 12 & 63 | 128), n.push(a >> 6 & 63 | 128), n.push(a & 63 | 128);
		} else n.push(r >> 12 | 224), n.push(r >> 6 & 63 | 128), n.push(r & 63 | 128);
	}
	return new Uint8Array(n);
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/hashes/esm/_assert.js
function cd(e) {
	if (!Number.isSafeInteger(e) || e < 0) throw Error(`Wrong positive integer: ${e}`);
}
function ld(e, ...t) {
	if (!(e instanceof Uint8Array)) throw Error("Expected Uint8Array");
	if (t.length > 0 && !t.includes(e.length)) throw Error(`Expected Uint8Array of length ${t}, not of length=${e.length}`);
}
function ud(e) {
	if (typeof e != "function" || typeof e.create != "function") throw Error("Hash should be wrapped by utils.wrapConstructor");
	cd(e.outputLen), cd(e.blockLen);
}
function dd(e, t = !0) {
	if (e.destroyed) throw Error("Hash instance has been destroyed");
	if (t && e.finished) throw Error("Hash#digest() has already been called");
}
function fd(e, t) {
	ld(e);
	let n = t.outputLen;
	if (e.length < n) throw Error(`digestInto() expects output buffer of length at least ${n}`);
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/hashes/esm/crypto.js
var pd = typeof globalThis == "object" && "crypto" in globalThis ? globalThis.crypto : void 0, md = (e) => e instanceof Uint8Array, hd = (e) => new Uint32Array(e.buffer, e.byteOffset, Math.floor(e.byteLength / 4)), gd = (e) => new DataView(e.buffer, e.byteOffset, e.byteLength), _d = (e, t) => e << 32 - t | e >>> t;
if (new Uint8Array(new Uint32Array([287454020]).buffer)[0] !== 68) throw Error("Non little-endian hardware is not supported");
function vd(e) {
	if (typeof e != "string") throw Error(`utf8ToBytes expected string, got ${typeof e}`);
	return new Uint8Array(new TextEncoder().encode(e));
}
function yd(e) {
	if (typeof e == "string" && (e = vd(e)), !md(e)) throw Error(`expected Uint8Array, got ${typeof e}`);
	return e;
}
function bd(...e) {
	let t = new Uint8Array(e.reduce((e, t) => e + t.length, 0)), n = 0;
	return e.forEach((e) => {
		if (!md(e)) throw Error("Uint8Array expected");
		t.set(e, n), n += e.length;
	}), t;
}
var xd = class {
	clone() {
		return this._cloneInto();
	}
};
({}).toString;
function Sd(e) {
	let t = (t) => e().update(yd(t)).digest(), n = e();
	return t.outputLen = n.outputLen, t.blockLen = n.blockLen, t.create = () => e(), t;
}
function Cd(e = 32) {
	if (pd && typeof pd.getRandomValues == "function") return pd.getRandomValues(new Uint8Array(e));
	throw Error("crypto.getRandomValues must be defined");
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/hashes/esm/hmac.js
var wd = class extends xd {
	constructor(e, t) {
		super(), this.finished = !1, this.destroyed = !1, ud(e);
		let n = yd(t);
		if (this.iHash = e.create(), typeof this.iHash.update != "function") throw Error("Expected instance of class which extends utils.Hash");
		this.blockLen = this.iHash.blockLen, this.outputLen = this.iHash.outputLen;
		let r = this.blockLen, i = new Uint8Array(r);
		i.set(n.length > r ? e.create().update(n).digest() : n);
		for (let e = 0; e < i.length; e++) i[e] ^= 54;
		this.iHash.update(i), this.oHash = e.create();
		for (let e = 0; e < i.length; e++) i[e] ^= 106;
		this.oHash.update(i), i.fill(0);
	}
	update(e) {
		return dd(this), this.iHash.update(e), this;
	}
	digestInto(e) {
		dd(this), ld(e, this.outputLen), this.finished = !0, this.iHash.digestInto(e), this.oHash.update(e), this.oHash.digestInto(e), this.destroy();
	}
	digest() {
		let e = new Uint8Array(this.oHash.outputLen);
		return this.digestInto(e), e;
	}
	_cloneInto(e) {
		e ||= Object.create(Object.getPrototypeOf(this), {});
		let { oHash: t, iHash: n, finished: r, destroyed: i, blockLen: a, outputLen: o } = this;
		return e = e, e.finished = r, e.destroyed = i, e.blockLen = a, e.outputLen = o, e.oHash = t._cloneInto(e.oHash), e.iHash = n._cloneInto(e.iHash), e;
	}
	destroy() {
		this.destroyed = !0, this.oHash.destroy(), this.iHash.destroy();
	}
}, Td = (e, t, n) => new wd(e, t).update(n).digest();
Td.create = (e, t) => new wd(e, t);
//#endregion
//#region node_modules/ethers/node_modules/@noble/hashes/esm/_sha2.js
function Ed(e, t, n, r) {
	if (typeof e.setBigUint64 == "function") return e.setBigUint64(t, n, r);
	let i = BigInt(32), a = BigInt(4294967295), o = Number(n >> i & a), s = Number(n & a), c = r ? 4 : 0, l = r ? 0 : 4;
	e.setUint32(t + c, o, r), e.setUint32(t + l, s, r);
}
var Dd = class extends xd {
	constructor(e, t, n, r) {
		super(), this.blockLen = e, this.outputLen = t, this.padOffset = n, this.isLE = r, this.finished = !1, this.length = 0, this.pos = 0, this.destroyed = !1, this.buffer = new Uint8Array(e), this.view = gd(this.buffer);
	}
	update(e) {
		dd(this);
		let { view: t, buffer: n, blockLen: r } = this;
		e = yd(e);
		let i = e.length;
		for (let a = 0; a < i;) {
			let o = Math.min(r - this.pos, i - a);
			if (o === r) {
				let t = gd(e);
				for (; r <= i - a; a += r) this.process(t, a);
				continue;
			}
			n.set(e.subarray(a, a + o), this.pos), this.pos += o, a += o, this.pos === r && (this.process(t, 0), this.pos = 0);
		}
		return this.length += e.length, this.roundClean(), this;
	}
	digestInto(e) {
		dd(this), fd(e, this), this.finished = !0;
		let { buffer: t, view: n, blockLen: r, isLE: i } = this, { pos: a } = this;
		t[a++] = 128, this.buffer.subarray(a).fill(0), this.padOffset > r - a && (this.process(n, 0), a = 0);
		for (let e = a; e < r; e++) t[e] = 0;
		Ed(n, r - 8, BigInt(this.length * 8), i), this.process(n, 0);
		let o = gd(e), s = this.outputLen;
		if (s % 4) throw Error("_sha2: outputLen should be aligned to 32bit");
		let c = s / 4, l = this.get();
		if (c > l.length) throw Error("_sha2: outputLen bigger than state");
		for (let e = 0; e < c; e++) o.setUint32(4 * e, l[e], i);
	}
	digest() {
		let { buffer: e, outputLen: t } = this;
		this.digestInto(e);
		let n = e.slice(0, t);
		return this.destroy(), n;
	}
	_cloneInto(e) {
		e ||= new this.constructor(), e.set(...this.get());
		let { blockLen: t, buffer: n, length: r, finished: i, destroyed: a, pos: o } = this;
		return e.length = r, e.pos = o, e.finished = i, e.destroyed = a, r % t && e.buffer.set(n), e;
	}
}, Od = (e, t, n) => e & t ^ ~e & n, kd = (e, t, n) => e & t ^ e & n ^ t & n, Ad = /* @__PURE__ */ new Uint32Array([
	1116352408,
	1899447441,
	3049323471,
	3921009573,
	961987163,
	1508970993,
	2453635748,
	2870763221,
	3624381080,
	310598401,
	607225278,
	1426881987,
	1925078388,
	2162078206,
	2614888103,
	3248222580,
	3835390401,
	4022224774,
	264347078,
	604807628,
	770255983,
	1249150122,
	1555081692,
	1996064986,
	2554220882,
	2821834349,
	2952996808,
	3210313671,
	3336571891,
	3584528711,
	113926993,
	338241895,
	666307205,
	773529912,
	1294757372,
	1396182291,
	1695183700,
	1986661051,
	2177026350,
	2456956037,
	2730485921,
	2820302411,
	3259730800,
	3345764771,
	3516065817,
	3600352804,
	4094571909,
	275423344,
	430227734,
	506948616,
	659060556,
	883997877,
	958139571,
	1322822218,
	1537002063,
	1747873779,
	1955562222,
	2024104815,
	2227730452,
	2361852424,
	2428436474,
	2756734187,
	3204031479,
	3329325298
]), jd = /* @__PURE__ */ new Uint32Array([
	1779033703,
	3144134277,
	1013904242,
	2773480762,
	1359893119,
	2600822924,
	528734635,
	1541459225
]), Md = /* @__PURE__ */ new Uint32Array(64), Nd = class extends Dd {
	constructor() {
		super(64, 32, 8, !1), this.A = jd[0] | 0, this.B = jd[1] | 0, this.C = jd[2] | 0, this.D = jd[3] | 0, this.E = jd[4] | 0, this.F = jd[5] | 0, this.G = jd[6] | 0, this.H = jd[7] | 0;
	}
	get() {
		let { A: e, B: t, C: n, D: r, E: i, F: a, G: o, H: s } = this;
		return [
			e,
			t,
			n,
			r,
			i,
			a,
			o,
			s
		];
	}
	set(e, t, n, r, i, a, o, s) {
		this.A = e | 0, this.B = t | 0, this.C = n | 0, this.D = r | 0, this.E = i | 0, this.F = a | 0, this.G = o | 0, this.H = s | 0;
	}
	process(e, t) {
		for (let n = 0; n < 16; n++, t += 4) Md[n] = e.getUint32(t, !1);
		for (let e = 16; e < 64; e++) {
			let t = Md[e - 15], n = Md[e - 2], r = _d(t, 7) ^ _d(t, 18) ^ t >>> 3;
			Md[e] = (_d(n, 17) ^ _d(n, 19) ^ n >>> 10) + Md[e - 7] + r + Md[e - 16] | 0;
		}
		let { A: n, B: r, C: i, D: a, E: o, F: s, G: c, H: l } = this;
		for (let e = 0; e < 64; e++) {
			let t = _d(o, 6) ^ _d(o, 11) ^ _d(o, 25), u = l + t + Od(o, s, c) + Ad[e] + Md[e] | 0, d = (_d(n, 2) ^ _d(n, 13) ^ _d(n, 22)) + kd(n, r, i) | 0;
			l = c, c = s, s = o, o = a + u | 0, a = i, i = r, r = n, n = u + d | 0;
		}
		n = n + this.A | 0, r = r + this.B | 0, i = i + this.C | 0, a = a + this.D | 0, o = o + this.E | 0, s = s + this.F | 0, c = c + this.G | 0, l = l + this.H | 0, this.set(n, r, i, a, o, s, c, l);
	}
	roundClean() {
		Md.fill(0);
	}
	destroy() {
		this.set(0, 0, 0, 0, 0, 0, 0, 0), this.buffer.fill(0);
	}
}, Pd = /* @__PURE__ */ Sd(() => new Nd()), Fd = /* @__PURE__ */ BigInt(2 ** 32 - 1), Id = /* @__PURE__ */ BigInt(32);
function Ld(e, t = !1) {
	return t ? {
		h: Number(e & Fd),
		l: Number(e >> Id & Fd)
	} : {
		h: Number(e >> Id & Fd) | 0,
		l: Number(e & Fd) | 0
	};
}
function Rd(e, t = !1) {
	let n = new Uint32Array(e.length), r = new Uint32Array(e.length);
	for (let i = 0; i < e.length; i++) {
		let { h: a, l: o } = Ld(e[i], t);
		[n[i], r[i]] = [a, o];
	}
	return [n, r];
}
var zd = (e, t, n) => e << n | t >>> 32 - n, Bd = (e, t, n) => t << n | e >>> 32 - n, Vd = (e, t, n) => t << n - 32 | e >>> 64 - n, Hd = (e, t, n) => e << n - 32 | t >>> 64 - n, [Ud, Wd, Gd] = [
	[],
	[],
	[]
], Kd = /* @__PURE__ */ BigInt(0), qd = /* @__PURE__ */ BigInt(1), Jd = /* @__PURE__ */ BigInt(2), Yd = /* @__PURE__ */ BigInt(7), Xd = /* @__PURE__ */ BigInt(256), Zd = /* @__PURE__ */ BigInt(113);
for (let e = 0, t = qd, n = 1, r = 0; e < 24; e++) {
	[n, r] = [r, (2 * n + 3 * r) % 5], Ud.push(2 * (5 * r + n)), Wd.push((e + 1) * (e + 2) / 2 % 64);
	let i = Kd;
	for (let e = 0; e < 7; e++) t = (t << qd ^ (t >> Yd) * Zd) % Xd, t & Jd && (i ^= qd << (qd << /* @__PURE__ */ BigInt(e)) - qd);
	Gd.push(i);
}
var [Qd, $d] = /* @__PURE__ */ Rd(Gd, !0), ef = (e, t, n) => n > 32 ? Vd(e, t, n) : zd(e, t, n), tf = (e, t, n) => n > 32 ? Hd(e, t, n) : Bd(e, t, n);
function nf(e, t = 24) {
	let n = new Uint32Array(10);
	for (let r = 24 - t; r < 24; r++) {
		for (let t = 0; t < 10; t++) n[t] = e[t] ^ e[t + 10] ^ e[t + 20] ^ e[t + 30] ^ e[t + 40];
		for (let t = 0; t < 10; t += 2) {
			let r = (t + 8) % 10, i = (t + 2) % 10, a = n[i], o = n[i + 1], s = ef(a, o, 1) ^ n[r], c = tf(a, o, 1) ^ n[r + 1];
			for (let n = 0; n < 50; n += 10) e[t + n] ^= s, e[t + n + 1] ^= c;
		}
		let t = e[2], i = e[3];
		for (let n = 0; n < 24; n++) {
			let r = Wd[n], a = ef(t, i, r), o = tf(t, i, r), s = Ud[n];
			t = e[s], i = e[s + 1], e[s] = a, e[s + 1] = o;
		}
		for (let t = 0; t < 50; t += 10) {
			for (let r = 0; r < 10; r++) n[r] = e[t + r];
			for (let r = 0; r < 10; r++) e[t + r] ^= ~n[(r + 2) % 10] & n[(r + 4) % 10];
		}
		e[0] ^= Qd[r], e[1] ^= $d[r];
	}
	n.fill(0);
}
var rf = class e extends xd {
	constructor(e, t, n, r = !1, i = 24) {
		if (super(), this.blockLen = e, this.suffix = t, this.outputLen = n, this.enableXOF = r, this.rounds = i, this.pos = 0, this.posOut = 0, this.finished = !1, this.destroyed = !1, cd(n), 0 >= this.blockLen || this.blockLen >= 200) throw Error("Sha3 supports only keccak-f1600 function");
		this.state = new Uint8Array(200), this.state32 = hd(this.state);
	}
	keccak() {
		nf(this.state32, this.rounds), this.posOut = 0, this.pos = 0;
	}
	update(e) {
		dd(this);
		let { blockLen: t, state: n } = this;
		e = yd(e);
		let r = e.length;
		for (let i = 0; i < r;) {
			let a = Math.min(t - this.pos, r - i);
			for (let t = 0; t < a; t++) n[this.pos++] ^= e[i++];
			this.pos === t && this.keccak();
		}
		return this;
	}
	finish() {
		if (this.finished) return;
		this.finished = !0;
		let { state: e, suffix: t, pos: n, blockLen: r } = this;
		e[n] ^= t, t & 128 && n === r - 1 && this.keccak(), e[r - 1] ^= 128, this.keccak();
	}
	writeInto(e) {
		dd(this, !1), ld(e), this.finish();
		let t = this.state, { blockLen: n } = this;
		for (let r = 0, i = e.length; r < i;) {
			this.posOut >= n && this.keccak();
			let a = Math.min(n - this.posOut, i - r);
			e.set(t.subarray(this.posOut, this.posOut + a), r), this.posOut += a, r += a;
		}
		return e;
	}
	xofInto(e) {
		if (!this.enableXOF) throw Error("XOF is not possible for this instance");
		return this.writeInto(e);
	}
	xof(e) {
		return cd(e), this.xofInto(new Uint8Array(e));
	}
	digestInto(e) {
		if (fd(e, this), this.finished) throw Error("digest() was already called");
		return this.writeInto(e), this.destroy(), e;
	}
	digest() {
		return this.digestInto(new Uint8Array(this.outputLen));
	}
	destroy() {
		this.destroyed = !0, this.state.fill(0);
	}
	_cloneInto(t) {
		let { blockLen: n, suffix: r, outputLen: i, rounds: a, enableXOF: o } = this;
		return t ||= new e(n, r, i, o, a), t.state32.set(this.state32), t.pos = this.pos, t.posOut = this.posOut, t.finished = this.finished, t.rounds = a, t.suffix = r, t.outputLen = i, t.enableXOF = o, t.destroyed = this.destroyed, t;
	}
}, af = /* @__PURE__ */ ((e, t, n) => Sd(() => new rf(t, e, n)))(1, 136, 256 / 8), of = !1, sf = function(e) {
	return af(e);
}, cf = sf;
function lf(e) {
	let t = Hu(e, "data");
	return Ku(cf(t));
}
lf._ = sf, lf.lock = function() {
	of = !0;
}, lf.register = function(e) {
	if (of) throw TypeError("keccak256 is locked");
	cf = e;
}, Object.freeze(lf);
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/abstract/utils.js
var uf = /* @__PURE__ */ c({
	bitGet: () => Af,
	bitLen: () => kf,
	bitMask: () => Mf,
	bitSet: () => jf,
	bytesToHex: () => gf,
	bytesToNumberBE: () => bf,
	bytesToNumberLE: () => xf,
	concatBytes: () => Ef,
	createHmacDrbg: () => Ff,
	ensureBytes: () => Tf,
	equalBytes: () => Df,
	hexToBytes: () => yf,
	hexToNumber: () => vf,
	numberToBytesBE: () => Sf,
	numberToBytesLE: () => Cf,
	numberToHexUnpadded: () => _f,
	numberToVarBytesBE: () => wf,
	utf8ToBytes: () => Of,
	validateObject: () => Lf
}), df = BigInt(0), ff = BigInt(1), pf = BigInt(2), mf = (e) => e instanceof Uint8Array, hf = /* @__PURE__ */ Array.from({ length: 256 }, (e, t) => t.toString(16).padStart(2, "0"));
function gf(e) {
	if (!mf(e)) throw Error("Uint8Array expected");
	let t = "";
	for (let n = 0; n < e.length; n++) t += hf[e[n]];
	return t;
}
function _f(e) {
	let t = e.toString(16);
	return t.length & 1 ? `0${t}` : t;
}
function vf(e) {
	if (typeof e != "string") throw Error("hex string expected, got " + typeof e);
	return BigInt(e === "" ? "0" : `0x${e}`);
}
function yf(e) {
	if (typeof e != "string") throw Error("hex string expected, got " + typeof e);
	let t = e.length;
	if (t % 2) throw Error("padded hex string expected, got unpadded hex of length " + t);
	let n = new Uint8Array(t / 2);
	for (let t = 0; t < n.length; t++) {
		let r = t * 2, i = e.slice(r, r + 2), a = Number.parseInt(i, 16);
		if (Number.isNaN(a) || a < 0) throw Error("Invalid byte sequence");
		n[t] = a;
	}
	return n;
}
function bf(e) {
	return vf(gf(e));
}
function xf(e) {
	if (!mf(e)) throw Error("Uint8Array expected");
	return vf(gf(Uint8Array.from(e).reverse()));
}
function Sf(e, t) {
	return yf(e.toString(16).padStart(t * 2, "0"));
}
function Cf(e, t) {
	return Sf(e, t).reverse();
}
function wf(e) {
	return yf(_f(e));
}
function Tf(e, t, n) {
	let r;
	if (typeof t == "string") try {
		r = yf(t);
	} catch (n) {
		throw Error(`${e} must be valid hex string, got "${t}". Cause: ${n}`);
	}
	else if (mf(t)) r = Uint8Array.from(t);
	else throw Error(`${e} must be hex string or Uint8Array`);
	let i = r.length;
	if (typeof n == "number" && i !== n) throw Error(`${e} expected ${n} bytes, got ${i}`);
	return r;
}
function Ef(...e) {
	let t = new Uint8Array(e.reduce((e, t) => e + t.length, 0)), n = 0;
	return e.forEach((e) => {
		if (!mf(e)) throw Error("Uint8Array expected");
		t.set(e, n), n += e.length;
	}), t;
}
function Df(e, t) {
	if (e.length !== t.length) return !1;
	for (let n = 0; n < e.length; n++) if (e[n] !== t[n]) return !1;
	return !0;
}
function Of(e) {
	if (typeof e != "string") throw Error(`utf8ToBytes expected string, got ${typeof e}`);
	return new Uint8Array(new TextEncoder().encode(e));
}
function kf(e) {
	let t;
	for (t = 0; e > df; e >>= ff, t += 1);
	return t;
}
function Af(e, t) {
	return e >> BigInt(t) & ff;
}
var jf = (e, t, n) => e | (n ? ff : df) << BigInt(t), Mf = (e) => (pf << BigInt(e - 1)) - ff, Nf = (e) => new Uint8Array(e), Pf = (e) => Uint8Array.from(e);
function Ff(e, t, n) {
	if (typeof e != "number" || e < 2) throw Error("hashLen must be a number");
	if (typeof t != "number" || t < 2) throw Error("qByteLen must be a number");
	if (typeof n != "function") throw Error("hmacFn must be a function");
	let r = Nf(e), i = Nf(e), a = 0, o = () => {
		r.fill(1), i.fill(0), a = 0;
	}, s = (...e) => n(i, r, ...e), c = (e = Nf()) => {
		i = s(Pf([0]), e), r = s(), e.length !== 0 && (i = s(Pf([1]), e), r = s());
	}, l = () => {
		if (a++ >= 1e3) throw Error("drbg: tried 1000 values");
		let e = 0, n = [];
		for (; e < t;) {
			r = s();
			let t = r.slice();
			n.push(t), e += r.length;
		}
		return Ef(...n);
	};
	return (e, t) => {
		o(), c(e);
		let n;
		for (; !(n = t(l()));) c();
		return o(), n;
	};
}
var If = {
	bigint: (e) => typeof e == "bigint",
	function: (e) => typeof e == "function",
	boolean: (e) => typeof e == "boolean",
	string: (e) => typeof e == "string",
	stringOrUint8Array: (e) => typeof e == "string" || e instanceof Uint8Array,
	isSafeInteger: (e) => Number.isSafeInteger(e),
	array: (e) => Array.isArray(e),
	field: (e, t) => t.Fp.isValid(e),
	hash: (e) => typeof e == "function" && Number.isSafeInteger(e.outputLen)
};
function Lf(e, t, n = {}) {
	let r = (t, n, r) => {
		let i = If[n];
		if (typeof i != "function") throw Error(`Invalid validator "${n}", expected function`);
		let a = e[t];
		if (!(r && a === void 0) && !i(a, e)) throw Error(`Invalid param ${String(t)}=${a} (${typeof a}), expected ${n}`);
	};
	for (let [e, n] of Object.entries(t)) r(e, n, !1);
	for (let [e, t] of Object.entries(n)) r(e, t, !0);
	return e;
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/abstract/modular.js
var Rf = BigInt(0), zf = BigInt(1), Bf = BigInt(2), Vf = BigInt(3), Hf = BigInt(4), Uf = BigInt(5), Wf = BigInt(8), Gf = BigInt(16);
function Kf(e, t) {
	let n = e % t;
	return n >= Rf ? n : t + n;
}
function qf(e, t, n) {
	if (n <= Rf || t < Rf) throw Error("Expected power/modulo > 0");
	if (n === zf) return Rf;
	let r = zf;
	for (; t > Rf;) t & zf && (r = r * e % n), e = e * e % n, t >>= zf;
	return r;
}
function Jf(e, t, n) {
	let r = e;
	for (; t-- > Rf;) r *= r, r %= n;
	return r;
}
function Yf(e, t) {
	if (e === Rf || t <= Rf) throw Error(`invert: expected positive integers, got n=${e} mod=${t}`);
	let n = Kf(e, t), r = t, i = Rf, a = zf, o = zf, s = Rf;
	for (; n !== Rf;) {
		let e = r / n, t = r % n, c = i - o * e, l = a - s * e;
		r = n, n = t, i = o, a = s, o = c, s = l;
	}
	if (r !== zf) throw Error("invert: does not exist");
	return Kf(i, t);
}
function Xf(e) {
	let t = (e - zf) / Bf, n, r, i;
	for (n = e - zf, r = 0; n % Bf === Rf; n /= Bf, r++);
	for (i = Bf; i < e && qf(i, t, e) !== e - zf; i++);
	if (r === 1) {
		let t = (e + zf) / Hf;
		return function(e, n) {
			let r = e.pow(n, t);
			if (!e.eql(e.sqr(r), n)) throw Error("Cannot find square root");
			return r;
		};
	}
	let a = (n + zf) / Bf;
	return function(e, o) {
		if (e.pow(o, t) === e.neg(e.ONE)) throw Error("Cannot find square root");
		let s = r, c = e.pow(e.mul(e.ONE, i), n), l = e.pow(o, a), u = e.pow(o, n);
		for (; !e.eql(u, e.ONE);) {
			if (e.eql(u, e.ZERO)) return e.ZERO;
			let t = 1;
			for (let n = e.sqr(u); t < s && !e.eql(n, e.ONE); t++) n = e.sqr(n);
			let n = e.pow(c, zf << BigInt(s - t - 1));
			c = e.sqr(n), l = e.mul(l, n), u = e.mul(u, c), s = t;
		}
		return l;
	};
}
function Zf(e) {
	if (e % Hf === Vf) {
		let t = (e + zf) / Hf;
		return function(e, n) {
			let r = e.pow(n, t);
			if (!e.eql(e.sqr(r), n)) throw Error("Cannot find square root");
			return r;
		};
	}
	if (e % Wf === Uf) {
		let t = (e - Uf) / Wf;
		return function(e, n) {
			let r = e.mul(n, Bf), i = e.pow(r, t), a = e.mul(n, i), o = e.mul(e.mul(a, Bf), i), s = e.mul(a, e.sub(o, e.ONE));
			if (!e.eql(e.sqr(s), n)) throw Error("Cannot find square root");
			return s;
		};
	}
	return e % Gf, Xf(e);
}
var Qf = [
	"create",
	"isValid",
	"is0",
	"neg",
	"inv",
	"sqrt",
	"sqr",
	"eql",
	"add",
	"sub",
	"mul",
	"pow",
	"div",
	"addN",
	"subN",
	"mulN",
	"sqrN"
];
function $f(e) {
	return Lf(e, Qf.reduce((e, t) => (e[t] = "function", e), {
		ORDER: "bigint",
		MASK: "bigint",
		BYTES: "isSafeInteger",
		BITS: "isSafeInteger"
	}));
}
function ep(e, t, n) {
	if (n < Rf) throw Error("Expected power > 0");
	if (n === Rf) return e.ONE;
	if (n === zf) return t;
	let r = e.ONE, i = t;
	for (; n > Rf;) n & zf && (r = e.mul(r, i)), i = e.sqr(i), n >>= zf;
	return r;
}
function tp(e, t) {
	let n = Array(t.length), r = t.reduce((t, r, i) => e.is0(r) ? t : (n[i] = t, e.mul(t, r)), e.ONE), i = e.inv(r);
	return t.reduceRight((t, r, i) => e.is0(r) ? t : (n[i] = e.mul(t, n[i]), e.mul(t, r)), i), n;
}
function np(e, t) {
	let n = t === void 0 ? e.toString(2).length : t;
	return {
		nBitLength: n,
		nByteLength: Math.ceil(n / 8)
	};
}
function rp(e, t, n = !1, r = {}) {
	if (e <= Rf) throw Error(`Expected Field ORDER > 0, got ${e}`);
	let { nBitLength: i, nByteLength: a } = np(e, t);
	if (a > 2048) throw Error("Field lengths over 2048 bytes are not supported");
	let o = Zf(e), s = Object.freeze({
		ORDER: e,
		BITS: i,
		BYTES: a,
		MASK: Mf(i),
		ZERO: Rf,
		ONE: zf,
		create: (t) => Kf(t, e),
		isValid: (t) => {
			if (typeof t != "bigint") throw Error(`Invalid field element: expected bigint, got ${typeof t}`);
			return Rf <= t && t < e;
		},
		is0: (e) => e === Rf,
		isOdd: (e) => (e & zf) === zf,
		neg: (t) => Kf(-t, e),
		eql: (e, t) => e === t,
		sqr: (t) => Kf(t * t, e),
		add: (t, n) => Kf(t + n, e),
		sub: (t, n) => Kf(t - n, e),
		mul: (t, n) => Kf(t * n, e),
		pow: (e, t) => ep(s, e, t),
		div: (t, n) => Kf(t * Yf(n, e), e),
		sqrN: (e) => e * e,
		addN: (e, t) => e + t,
		subN: (e, t) => e - t,
		mulN: (e, t) => e * t,
		inv: (t) => Yf(t, e),
		sqrt: r.sqrt || ((e) => o(s, e)),
		invertBatch: (e) => tp(s, e),
		cmov: (e, t, n) => n ? t : e,
		toBytes: (e) => n ? Cf(e, a) : Sf(e, a),
		fromBytes: (e) => {
			if (e.length !== a) throw Error(`Fp.fromBytes: expected ${a}, got ${e.length}`);
			return n ? xf(e) : bf(e);
		}
	});
	return Object.freeze(s);
}
function ip(e) {
	if (typeof e != "bigint") throw Error("field order must be bigint");
	let t = e.toString(2).length;
	return Math.ceil(t / 8);
}
function ap(e) {
	let t = ip(e);
	return t + Math.ceil(t / 2);
}
function op(e, t, n = !1) {
	let r = e.length, i = ip(t), a = ap(t);
	if (r < 16 || r < a || r > 1024) throw Error(`expected ${a}-1024 bytes of input, got ${r}`);
	let o = Kf(n ? bf(e) : xf(e), t - zf) + zf;
	return n ? Cf(o, i) : Sf(o, i);
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/abstract/curve.js
var sp = BigInt(0), cp = BigInt(1);
function lp(e, t) {
	let n = (e, t) => {
		let n = t.negate();
		return e ? n : t;
	}, r = (e) => ({
		windows: Math.ceil(t / e) + 1,
		windowSize: 2 ** (e - 1)
	});
	return {
		constTimeNegate: n,
		unsafeLadder(t, n) {
			let r = e.ZERO, i = t;
			for (; n > sp;) n & cp && (r = r.add(i)), i = i.double(), n >>= cp;
			return r;
		},
		precomputeWindow(e, t) {
			let { windows: n, windowSize: i } = r(t), a = [], o = e, s = o;
			for (let e = 0; e < n; e++) {
				s = o, a.push(s);
				for (let e = 1; e < i; e++) s = s.add(o), a.push(s);
				o = s.double();
			}
			return a;
		},
		wNAF(t, i, a) {
			let { windows: o, windowSize: s } = r(t), c = e.ZERO, l = e.BASE, u = BigInt(2 ** t - 1), d = 2 ** t, f = BigInt(t);
			for (let e = 0; e < o; e++) {
				let t = e * s, r = Number(a & u);
				a >>= f, r > s && (r -= d, a += cp);
				let o = t, p = t + Math.abs(r) - 1, m = e % 2 != 0, h = r < 0;
				r === 0 ? l = l.add(n(m, i[o])) : c = c.add(n(h, i[p]));
			}
			return {
				p: c,
				f: l
			};
		},
		wNAFCached(e, t, n, r) {
			let i = e._WINDOW_SIZE || 1, a = t.get(e);
			return a || (a = this.precomputeWindow(e, i), i !== 1 && t.set(e, r(a))), this.wNAF(i, a, n);
		}
	};
}
function up(e) {
	return $f(e.Fp), Lf(e, {
		n: "bigint",
		h: "bigint",
		Gx: "field",
		Gy: "field"
	}, {
		nBitLength: "isSafeInteger",
		nByteLength: "isSafeInteger"
	}), Object.freeze({
		...np(e.n, e.nBitLength),
		...e,
		p: e.Fp.ORDER
	});
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/abstract/weierstrass.js
function dp(e) {
	let t = up(e);
	Lf(t, {
		a: "field",
		b: "field"
	}, {
		allowedPrivateKeyLengths: "array",
		wrapPrivateKey: "boolean",
		isTorsionFree: "function",
		clearCofactor: "function",
		allowInfinityPoint: "boolean",
		fromBytes: "function",
		toBytes: "function"
	});
	let { endo: n, Fp: r, a: i } = t;
	if (n) {
		if (!r.eql(i, r.ZERO)) throw Error("Endomorphism can only be defined for Koblitz curves that have a=0");
		if (typeof n != "object" || typeof n.beta != "bigint" || typeof n.splitScalar != "function") throw Error("Expected endomorphism with beta: bigint and splitScalar: function");
	}
	return Object.freeze({ ...t });
}
var { bytesToNumberBE: fp, hexToBytes: pp } = uf, mp = {
	Err: class extends Error {
		constructor(e = "") {
			super(e);
		}
	},
	_parseInt(e) {
		let { Err: t } = mp;
		if (e.length < 2 || e[0] !== 2) throw new t("Invalid signature integer tag");
		let n = e[1], r = e.subarray(2, n + 2);
		if (!n || r.length !== n) throw new t("Invalid signature integer: wrong length");
		if (r[0] & 128) throw new t("Invalid signature integer: negative");
		if (r[0] === 0 && !(r[1] & 128)) throw new t("Invalid signature integer: unnecessary leading zero");
		return {
			d: fp(r),
			l: e.subarray(n + 2)
		};
	},
	toSig(e) {
		let { Err: t } = mp, n = typeof e == "string" ? pp(e) : e;
		if (!(n instanceof Uint8Array)) throw Error("ui8a expected");
		let r = n.length;
		if (r < 2 || n[0] != 48) throw new t("Invalid signature tag");
		if (n[1] !== r - 2) throw new t("Invalid signature: incorrect length");
		let { d: i, l: a } = mp._parseInt(n.subarray(2)), { d: o, l: s } = mp._parseInt(a);
		if (s.length) throw new t("Invalid signature: left bytes after parsing");
		return {
			r: i,
			s: o
		};
	},
	hexFromSig(e) {
		let t = (e) => Number.parseInt(e[0], 16) & 8 ? "00" + e : e, n = (e) => {
			let t = e.toString(16);
			return t.length & 1 ? `0${t}` : t;
		}, r = t(n(e.s)), i = t(n(e.r)), a = r.length / 2, o = i.length / 2, s = n(a), c = n(o);
		return `30${n(o + a + 4)}02${c}${i}02${s}${r}`;
	}
}, hp = BigInt(0), gp = BigInt(1), _p = BigInt(2), vp = BigInt(3), yp = BigInt(4);
function bp(e) {
	let t = dp(e), { Fp: n } = t, r = t.toBytes || ((e, t, r) => {
		let i = t.toAffine();
		return Ef(Uint8Array.from([4]), n.toBytes(i.x), n.toBytes(i.y));
	}), i = t.fromBytes || ((e) => {
		let t = e.subarray(1);
		return {
			x: n.fromBytes(t.subarray(0, n.BYTES)),
			y: n.fromBytes(t.subarray(n.BYTES, 2 * n.BYTES))
		};
	});
	function a(e) {
		let { a: r, b: i } = t, a = n.sqr(e), o = n.mul(a, e);
		return n.add(n.add(o, n.mul(e, r)), i);
	}
	if (!n.eql(n.sqr(t.Gy), a(t.Gx))) throw Error("bad generator point: equation left != right");
	function o(e) {
		return typeof e == "bigint" && hp < e && e < t.n;
	}
	function s(e) {
		if (!o(e)) throw Error("Expected valid bigint: 0 < bigint < curve.n");
	}
	function c(e) {
		let { allowedPrivateKeyLengths: n, nByteLength: r, wrapPrivateKey: i, n: a } = t;
		if (n && typeof e != "bigint") {
			if (e instanceof Uint8Array && (e = gf(e)), typeof e != "string" || !n.includes(e.length)) throw Error("Invalid key");
			e = e.padStart(r * 2, "0");
		}
		let o;
		try {
			o = typeof e == "bigint" ? e : bf(Tf("private key", e, r));
		} catch {
			throw Error(`private key must be ${r} bytes, hex or bigint, not ${typeof e}`);
		}
		return i && (o = Kf(o, a)), s(o), o;
	}
	let l = /* @__PURE__ */ new Map();
	function u(e) {
		if (!(e instanceof d)) throw Error("ProjectivePoint expected");
	}
	class d {
		constructor(e, t, r) {
			if (this.px = e, this.py = t, this.pz = r, e == null || !n.isValid(e)) throw Error("x required");
			if (t == null || !n.isValid(t)) throw Error("y required");
			if (r == null || !n.isValid(r)) throw Error("z required");
		}
		static fromAffine(e) {
			let { x: t, y: r } = e || {};
			if (!e || !n.isValid(t) || !n.isValid(r)) throw Error("invalid affine point");
			if (e instanceof d) throw Error("projective point not allowed");
			let i = (e) => n.eql(e, n.ZERO);
			return i(t) && i(r) ? d.ZERO : new d(t, r, n.ONE);
		}
		get x() {
			return this.toAffine().x;
		}
		get y() {
			return this.toAffine().y;
		}
		static normalizeZ(e) {
			let t = n.invertBatch(e.map((e) => e.pz));
			return e.map((e, n) => e.toAffine(t[n])).map(d.fromAffine);
		}
		static fromHex(e) {
			let t = d.fromAffine(i(Tf("pointHex", e)));
			return t.assertValidity(), t;
		}
		static fromPrivateKey(e) {
			return d.BASE.multiply(c(e));
		}
		_setWindowSize(e) {
			this._WINDOW_SIZE = e, l.delete(this);
		}
		assertValidity() {
			if (this.is0()) {
				if (t.allowInfinityPoint && !n.is0(this.py)) return;
				throw Error("bad point: ZERO");
			}
			let { x: e, y: r } = this.toAffine();
			if (!n.isValid(e) || !n.isValid(r)) throw Error("bad point: x or y not FE");
			let i = n.sqr(r), o = a(e);
			if (!n.eql(i, o)) throw Error("bad point: equation left != right");
			if (!this.isTorsionFree()) throw Error("bad point: not in prime-order subgroup");
		}
		hasEvenY() {
			let { y: e } = this.toAffine();
			if (n.isOdd) return !n.isOdd(e);
			throw Error("Field doesn't support isOdd");
		}
		equals(e) {
			u(e);
			let { px: t, py: r, pz: i } = this, { px: a, py: o, pz: s } = e, c = n.eql(n.mul(t, s), n.mul(a, i)), l = n.eql(n.mul(r, s), n.mul(o, i));
			return c && l;
		}
		negate() {
			return new d(this.px, n.neg(this.py), this.pz);
		}
		double() {
			let { a: e, b: r } = t, i = n.mul(r, vp), { px: a, py: o, pz: s } = this, c = n.ZERO, l = n.ZERO, u = n.ZERO, f = n.mul(a, a), p = n.mul(o, o), m = n.mul(s, s), h = n.mul(a, o);
			return h = n.add(h, h), u = n.mul(a, s), u = n.add(u, u), c = n.mul(e, u), l = n.mul(i, m), l = n.add(c, l), c = n.sub(p, l), l = n.add(p, l), l = n.mul(c, l), c = n.mul(h, c), u = n.mul(i, u), m = n.mul(e, m), h = n.sub(f, m), h = n.mul(e, h), h = n.add(h, u), u = n.add(f, f), f = n.add(u, f), f = n.add(f, m), f = n.mul(f, h), l = n.add(l, f), m = n.mul(o, s), m = n.add(m, m), f = n.mul(m, h), c = n.sub(c, f), u = n.mul(m, p), u = n.add(u, u), u = n.add(u, u), new d(c, l, u);
		}
		add(e) {
			u(e);
			let { px: r, py: i, pz: a } = this, { px: o, py: s, pz: c } = e, l = n.ZERO, f = n.ZERO, p = n.ZERO, m = t.a, h = n.mul(t.b, vp), g = n.mul(r, o), _ = n.mul(i, s), v = n.mul(a, c), y = n.add(r, i), b = n.add(o, s);
			y = n.mul(y, b), b = n.add(g, _), y = n.sub(y, b), b = n.add(r, a);
			let x = n.add(o, c);
			return b = n.mul(b, x), x = n.add(g, v), b = n.sub(b, x), x = n.add(i, a), l = n.add(s, c), x = n.mul(x, l), l = n.add(_, v), x = n.sub(x, l), p = n.mul(m, b), l = n.mul(h, v), p = n.add(l, p), l = n.sub(_, p), p = n.add(_, p), f = n.mul(l, p), _ = n.add(g, g), _ = n.add(_, g), v = n.mul(m, v), b = n.mul(h, b), _ = n.add(_, v), v = n.sub(g, v), v = n.mul(m, v), b = n.add(b, v), g = n.mul(_, b), f = n.add(f, g), g = n.mul(x, b), l = n.mul(y, l), l = n.sub(l, g), g = n.mul(y, _), p = n.mul(x, p), p = n.add(p, g), new d(l, f, p);
		}
		subtract(e) {
			return this.add(e.negate());
		}
		is0() {
			return this.equals(d.ZERO);
		}
		wNAF(e) {
			return p.wNAFCached(this, l, e, (e) => {
				let t = n.invertBatch(e.map((e) => e.pz));
				return e.map((e, n) => e.toAffine(t[n])).map(d.fromAffine);
			});
		}
		multiplyUnsafe(e) {
			let r = d.ZERO;
			if (e === hp) return r;
			if (s(e), e === gp) return this;
			let { endo: i } = t;
			if (!i) return p.unsafeLadder(this, e);
			let { k1neg: a, k1: o, k2neg: c, k2: l } = i.splitScalar(e), u = r, f = r, m = this;
			for (; o > hp || l > hp;) o & gp && (u = u.add(m)), l & gp && (f = f.add(m)), m = m.double(), o >>= gp, l >>= gp;
			return a && (u = u.negate()), c && (f = f.negate()), f = new d(n.mul(f.px, i.beta), f.py, f.pz), u.add(f);
		}
		multiply(e) {
			s(e);
			let r = e, i, a, { endo: o } = t;
			if (o) {
				let { k1neg: e, k1: t, k2neg: s, k2: c } = o.splitScalar(r), { p: l, f: u } = this.wNAF(t), { p: f, f: m } = this.wNAF(c);
				l = p.constTimeNegate(e, l), f = p.constTimeNegate(s, f), f = new d(n.mul(f.px, o.beta), f.py, f.pz), i = l.add(f), a = u.add(m);
			} else {
				let { p: e, f: t } = this.wNAF(r);
				i = e, a = t;
			}
			return d.normalizeZ([i, a])[0];
		}
		multiplyAndAddUnsafe(e, t, n) {
			let r = d.BASE, i = (e, t) => t === hp || t === gp || !e.equals(r) ? e.multiplyUnsafe(t) : e.multiply(t), a = i(this, t).add(i(e, n));
			return a.is0() ? void 0 : a;
		}
		toAffine(e) {
			let { px: t, py: r, pz: i } = this, a = this.is0();
			e ??= a ? n.ONE : n.inv(i);
			let o = n.mul(t, e), s = n.mul(r, e), c = n.mul(i, e);
			if (a) return {
				x: n.ZERO,
				y: n.ZERO
			};
			if (!n.eql(c, n.ONE)) throw Error("invZ was invalid");
			return {
				x: o,
				y: s
			};
		}
		isTorsionFree() {
			let { h: e, isTorsionFree: n } = t;
			if (e === gp) return !0;
			if (n) return n(d, this);
			throw Error("isTorsionFree() has not been declared for the elliptic curve");
		}
		clearCofactor() {
			let { h: e, clearCofactor: n } = t;
			return e === gp ? this : n ? n(d, this) : this.multiplyUnsafe(t.h);
		}
		toRawBytes(e = !0) {
			return this.assertValidity(), r(d, this, e);
		}
		toHex(e = !0) {
			return gf(this.toRawBytes(e));
		}
	}
	d.BASE = new d(t.Gx, t.Gy, n.ONE), d.ZERO = new d(n.ZERO, n.ONE, n.ZERO);
	let f = t.nBitLength, p = lp(d, t.endo ? Math.ceil(f / 2) : f);
	return {
		CURVE: t,
		ProjectivePoint: d,
		normPrivateKeyToScalar: c,
		weierstrassEquation: a,
		isWithinCurveOrder: o
	};
}
function xp(e) {
	let t = up(e);
	return Lf(t, {
		hash: "hash",
		hmac: "function",
		randomBytes: "function"
	}, {
		bits2int: "function",
		bits2int_modN: "function",
		lowS: "boolean"
	}), Object.freeze({
		lowS: !0,
		...t
	});
}
function Sp(e) {
	let t = xp(e), { Fp: n, n: r } = t, i = n.BYTES + 1, a = 2 * n.BYTES + 1;
	function o(e) {
		return hp < e && e < n.ORDER;
	}
	function s(e) {
		return Kf(e, r);
	}
	function c(e) {
		return Yf(e, r);
	}
	let { ProjectivePoint: l, normPrivateKeyToScalar: u, weierstrassEquation: d, isWithinCurveOrder: f } = bp({
		...t,
		toBytes(e, t, r) {
			let i = t.toAffine(), a = n.toBytes(i.x), o = Ef;
			return r ? o(Uint8Array.from([t.hasEvenY() ? 2 : 3]), a) : o(Uint8Array.from([4]), a, n.toBytes(i.y));
		},
		fromBytes(e) {
			let t = e.length, r = e[0], s = e.subarray(1);
			if (t === i && (r === 2 || r === 3)) {
				let e = bf(s);
				if (!o(e)) throw Error("Point is not on curve");
				let t = d(e), i = n.sqrt(t), a = (i & gp) === gp;
				return (r & 1) == 1 !== a && (i = n.neg(i)), {
					x: e,
					y: i
				};
			} else if (t === a && r === 4) return {
				x: n.fromBytes(s.subarray(0, n.BYTES)),
				y: n.fromBytes(s.subarray(n.BYTES, 2 * n.BYTES))
			};
			else throw Error(`Point of length ${t} was invalid. Expected ${i} compressed bytes or ${a} uncompressed bytes`);
		}
	}), p = (e) => gf(Sf(e, t.nByteLength));
	function m(e) {
		return e > r >> gp;
	}
	function h(e) {
		return m(e) ? s(-e) : e;
	}
	let g = (e, t, n) => bf(e.slice(t, n));
	class _ {
		constructor(e, t, n) {
			this.r = e, this.s = t, this.recovery = n, this.assertValidity();
		}
		static fromCompact(e) {
			let n = t.nByteLength;
			return e = Tf("compactSignature", e, n * 2), new _(g(e, 0, n), g(e, n, 2 * n));
		}
		static fromDER(e) {
			let { r: t, s: n } = mp.toSig(Tf("DER", e));
			return new _(t, n);
		}
		assertValidity() {
			if (!f(this.r)) throw Error("r must be 0 < r < CURVE.n");
			if (!f(this.s)) throw Error("s must be 0 < s < CURVE.n");
		}
		addRecoveryBit(e) {
			return new _(this.r, this.s, e);
		}
		recoverPublicKey(e) {
			let { r, s: i, recovery: a } = this, o = C(Tf("msgHash", e));
			if (a == null || ![
				0,
				1,
				2,
				3
			].includes(a)) throw Error("recovery id invalid");
			let u = a === 2 || a === 3 ? r + t.n : r;
			if (u >= n.ORDER) throw Error("recovery id 2 or 3 invalid");
			let d = a & 1 ? "03" : "02", f = l.fromHex(d + p(u)), m = c(u), h = s(-o * m), g = s(i * m), _ = l.BASE.multiplyAndAddUnsafe(f, h, g);
			if (!_) throw Error("point at infinify");
			return _.assertValidity(), _;
		}
		hasHighS() {
			return m(this.s);
		}
		normalizeS() {
			return this.hasHighS() ? new _(this.r, s(-this.s), this.recovery) : this;
		}
		toDERRawBytes() {
			return yf(this.toDERHex());
		}
		toDERHex() {
			return mp.hexFromSig({
				r: this.r,
				s: this.s
			});
		}
		toCompactRawBytes() {
			return yf(this.toCompactHex());
		}
		toCompactHex() {
			return p(this.r) + p(this.s);
		}
	}
	let v = {
		isValidPrivateKey(e) {
			try {
				return u(e), !0;
			} catch {
				return !1;
			}
		},
		normPrivateKeyToScalar: u,
		randomPrivateKey: () => {
			let e = ap(t.n);
			return op(t.randomBytes(e), t.n);
		},
		precompute(e = 8, t = l.BASE) {
			return t._setWindowSize(e), t.multiply(BigInt(3)), t;
		}
	};
	function y(e, t = !0) {
		return l.fromPrivateKey(e).toRawBytes(t);
	}
	function b(e) {
		let t = e instanceof Uint8Array, n = typeof e == "string", r = (t || n) && e.length;
		return t ? r === i || r === a : n ? r === 2 * i || r === 2 * a : e instanceof l;
	}
	function x(e, t, n = !0) {
		if (b(e)) throw Error("first arg must be private key");
		if (!b(t)) throw Error("second arg must be public key");
		return l.fromHex(t).multiply(u(e)).toRawBytes(n);
	}
	let S = t.bits2int || function(e) {
		let n = bf(e), r = e.length * 8 - t.nBitLength;
		return r > 0 ? n >> BigInt(r) : n;
	}, C = t.bits2int_modN || function(e) {
		return s(S(e));
	}, w = Mf(t.nBitLength);
	function T(e) {
		if (typeof e != "bigint") throw Error("bigint expected");
		if (!(hp <= e && e < w)) throw Error(`bigint expected < 2^${t.nBitLength}`);
		return Sf(e, t.nByteLength);
	}
	function E(e, r, i = D) {
		if (["recovered", "canonical"].some((e) => e in i)) throw Error("sign() legacy options not supported");
		let { hash: a, randomBytes: o } = t, { lowS: d, prehash: p, extraEntropy: g } = i;
		d ??= !0, e = Tf("msgHash", e), p && (e = Tf("prehashed msgHash", a(e)));
		let v = C(e), y = u(r), b = [T(y), T(v)];
		if (g != null) {
			let e = g === !0 ? o(n.BYTES) : g;
			b.push(Tf("extraEntropy", e));
		}
		let x = Ef(...b), w = v;
		function E(e) {
			let t = S(e);
			if (!f(t)) return;
			let n = c(t), r = l.BASE.multiply(t).toAffine(), i = s(r.x);
			if (i === hp) return;
			let a = s(n * s(w + i * y));
			if (a === hp) return;
			let o = (r.x === i ? 0 : 2) | Number(r.y & gp), u = a;
			return d && m(a) && (u = h(a), o ^= 1), new _(i, u, o);
		}
		return {
			seed: x,
			k2sig: E
		};
	}
	let D = {
		lowS: t.lowS,
		prehash: !1
	}, ee = {
		lowS: t.lowS,
		prehash: !1
	};
	function O(e, n, r = D) {
		let { seed: i, k2sig: a } = E(e, n, r), o = t;
		return Ff(o.hash.outputLen, o.nByteLength, o.hmac)(i, a);
	}
	l.BASE._setWindowSize(8);
	function k(e, n, r, i = ee) {
		let a = e;
		if (n = Tf("msgHash", n), r = Tf("publicKey", r), "strict" in i) throw Error("options.strict was renamed to lowS");
		let { lowS: o, prehash: u } = i, d, f;
		try {
			if (typeof a == "string" || a instanceof Uint8Array) try {
				d = _.fromDER(a);
			} catch (e) {
				if (!(e instanceof mp.Err)) throw e;
				d = _.fromCompact(a);
			}
			else if (typeof a == "object" && typeof a.r == "bigint" && typeof a.s == "bigint") {
				let { r: e, s: t } = a;
				d = new _(e, t);
			} else throw Error("PARSE");
			f = l.fromHex(r);
		} catch (e) {
			if (e.message === "PARSE") throw Error("signature must be Signature instance, Uint8Array or hex string");
			return !1;
		}
		if (o && d.hasHighS()) return !1;
		u && (n = t.hash(n));
		let { r: p, s: m } = d, h = C(n), g = c(m), v = s(h * g), y = s(p * g), b = l.BASE.multiplyAndAddUnsafe(f, v, y)?.toAffine();
		return b ? s(b.x) === p : !1;
	}
	return {
		CURVE: t,
		getPublicKey: y,
		getSharedSecret: x,
		sign: O,
		verify: k,
		ProjectivePoint: l,
		Signature: _,
		utils: v
	};
}
function Cp(e, t) {
	let n = e.ORDER, r = hp;
	for (let e = n - gp; e % _p === hp; e /= _p) r += gp;
	let i = r, a = _p << i - gp - gp, o = a * _p, s = (n - gp) / o, c = (s - gp) / _p, l = o - gp, u = a, d = e.pow(t, s), f = e.pow(t, (s + gp) / _p), p = (t, n) => {
		let r = d, a = e.pow(n, l), o = e.sqr(a);
		o = e.mul(o, n);
		let s = e.mul(t, o);
		s = e.pow(s, c), s = e.mul(s, a), a = e.mul(s, n), o = e.mul(s, t);
		let p = e.mul(o, a);
		s = e.pow(p, u);
		let m = e.eql(s, e.ONE);
		a = e.mul(o, f), s = e.mul(p, r), o = e.cmov(a, o, m), p = e.cmov(s, p, m);
		for (let t = i; t > gp; t--) {
			let n = t - _p;
			n = _p << n - gp;
			let i = e.pow(p, n), s = e.eql(i, e.ONE);
			a = e.mul(o, r), r = e.mul(r, r), i = e.mul(p, r), o = e.cmov(a, o, s), p = e.cmov(i, p, s);
		}
		return {
			isValid: m,
			value: o
		};
	};
	if (e.ORDER % yp === vp) {
		let n = (e.ORDER - vp) / yp, r = e.sqrt(e.neg(t));
		p = (t, i) => {
			let a = e.sqr(i), o = e.mul(t, i);
			a = e.mul(a, o);
			let s = e.pow(a, n);
			s = e.mul(s, o);
			let c = e.mul(s, r), l = e.mul(e.sqr(s), i), u = e.eql(l, t);
			return {
				isValid: u,
				value: e.cmov(c, s, u)
			};
		};
	}
	return p;
}
function wp(e, t) {
	if ($f(e), !e.isValid(t.A) || !e.isValid(t.B) || !e.isValid(t.Z)) throw Error("mapToCurveSimpleSWU: invalid opts");
	let n = Cp(e, t.Z);
	if (!e.isOdd) throw Error("Fp.isOdd is not implemented!");
	return (r) => {
		let i, a, o, s, c, l, u, d;
		i = e.sqr(r), i = e.mul(i, t.Z), a = e.sqr(i), a = e.add(a, i), o = e.add(a, e.ONE), o = e.mul(o, t.B), s = e.cmov(t.Z, e.neg(a), !e.eql(a, e.ZERO)), s = e.mul(s, t.A), a = e.sqr(o), l = e.sqr(s), c = e.mul(l, t.A), a = e.add(a, c), a = e.mul(a, o), l = e.mul(l, s), c = e.mul(l, t.B), a = e.add(a, c), u = e.mul(i, o);
		let { isValid: f, value: p } = n(a, l);
		d = e.mul(i, r), d = e.mul(d, p), u = e.cmov(u, o, f), d = e.cmov(d, p, f);
		let m = e.isOdd(r) === e.isOdd(d);
		return d = e.cmov(e.neg(d), d, m), u = e.div(u, s), {
			x: u,
			y: d
		};
	};
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/abstract/hash-to-curve.js
function Tp(e) {
	if (e instanceof Uint8Array) return e;
	if (typeof e == "string") return Of(e);
	throw Error("DST must be Uint8Array or string");
}
var Ep = bf;
function Dp(e, t) {
	if (e < 0 || e >= 1 << 8 * t) throw Error(`bad I2OSP call: value=${e} length=${t}`);
	let n = Array.from({ length: t }).fill(0);
	for (let r = t - 1; r >= 0; r--) n[r] = e & 255, e >>>= 8;
	return new Uint8Array(n);
}
function Op(e, t) {
	let n = new Uint8Array(e.length);
	for (let r = 0; r < e.length; r++) n[r] = e[r] ^ t[r];
	return n;
}
function kp(e) {
	if (!(e instanceof Uint8Array)) throw Error("Uint8Array expected");
}
function Ap(e) {
	if (!Number.isSafeInteger(e)) throw Error("number expected");
}
function jp(e, t, n, r) {
	kp(e), kp(t), Ap(n), t.length > 255 && (t = r(Ef(Of("H2C-OVERSIZE-DST-"), t)));
	let { outputLen: i, blockLen: a } = r, o = Math.ceil(n / i);
	if (o > 255) throw Error("Invalid xmd length");
	let s = Ef(t, Dp(t.length, 1)), c = Dp(0, a), l = Dp(n, 2), u = Array(o), d = r(Ef(c, e, l, Dp(0, 1), s));
	u[0] = r(Ef(d, Dp(1, 1), s));
	for (let e = 1; e <= o; e++) u[e] = r(Ef(Op(d, u[e - 1]), Dp(e + 1, 1), s));
	return Ef(...u).slice(0, n);
}
function Mp(e, t, n, r, i) {
	if (kp(e), kp(t), Ap(n), t.length > 255) {
		let e = Math.ceil(2 * r / 8);
		t = i.create({ dkLen: e }).update(Of("H2C-OVERSIZE-DST-")).update(t).digest();
	}
	if (n > 65535 || t.length > 255) throw Error("expand_message_xof: invalid lenInBytes");
	return i.create({ dkLen: n }).update(e).update(Dp(n, 2)).update(t).update(Dp(t.length, 1)).digest();
}
function Np(e, t, n) {
	Lf(n, {
		DST: "stringOrUint8Array",
		p: "bigint",
		m: "isSafeInteger",
		k: "isSafeInteger",
		hash: "hash"
	});
	let { p: r, k: i, m: a, hash: o, expand: s, DST: c } = n;
	kp(e), Ap(t);
	let l = Tp(c), u = r.toString(2).length, d = Math.ceil((u + i) / 8), f = t * a * d, p;
	if (s === "xmd") p = jp(e, l, f, o);
	else if (s === "xof") p = Mp(e, l, f, i, o);
	else if (s === "_internal_pass") p = e;
	else throw Error("expand must be \"xmd\" or \"xof\"");
	let m = Array(t);
	for (let e = 0; e < t; e++) {
		let t = Array(a);
		for (let n = 0; n < a; n++) {
			let i = d * (n + e * a);
			t[n] = Kf(Ep(p.subarray(i, i + d)), r);
		}
		m[e] = t;
	}
	return m;
}
function Pp(e, t) {
	let n = t.map((e) => Array.from(e).reverse());
	return (t, r) => {
		let [i, a, o, s] = n.map((n) => n.reduce((n, r) => e.add(e.mul(n, t), r)));
		return t = e.div(i, a), r = e.mul(r, e.div(o, s)), {
			x: t,
			y: r
		};
	};
}
function Fp(e, t, n) {
	if (typeof t != "function") throw Error("mapToCurve() must be defined");
	return {
		hashToCurve(r, i) {
			let a = Np(r, 2, {
				...n,
				DST: n.DST,
				...i
			}), o = e.fromAffine(t(a[0])), s = e.fromAffine(t(a[1])), c = o.add(s).clearCofactor();
			return c.assertValidity(), c;
		},
		encodeToCurve(r, i) {
			let a = Np(r, 1, {
				...n,
				DST: n.encodeDST,
				...i
			}), o = e.fromAffine(t(a[0])).clearCofactor();
			return o.assertValidity(), o;
		}
	};
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/_shortw_utils.js
function Ip(e) {
	return {
		hash: e,
		hmac: (t, ...n) => Td(e, t, bd(...n)),
		randomBytes: Cd
	};
}
function Lp(e, t) {
	let n = (t) => Sp({
		...e,
		...Ip(t)
	});
	return Object.freeze({
		...n(t),
		create: n
	});
}
//#endregion
//#region node_modules/ethers/node_modules/@noble/curves/esm/secp256k1.js
var Rp = BigInt("0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"), zp = BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"), Bp = BigInt(1), Vp = BigInt(2), Hp = (e, t) => (e + t / Vp) / t;
function Up(e) {
	let t = Rp, n = BigInt(3), r = BigInt(6), i = BigInt(11), a = BigInt(22), o = BigInt(23), s = BigInt(44), c = BigInt(88), l = e * e * e % t, u = l * l * e % t, d = Jf(Jf(Jf(u, n, t) * u % t, n, t) * u % t, Vp, t) * l % t, f = Jf(d, i, t) * d % t, p = Jf(f, a, t) * f % t, m = Jf(p, s, t) * p % t, h = Jf(Jf(Jf(Jf(Jf(Jf(m, c, t) * m % t, s, t) * p % t, n, t) * u % t, o, t) * f % t, r, t) * l % t, Vp, t);
	if (!Wp.eql(Wp.sqr(h), e)) throw Error("Cannot find square root");
	return h;
}
var Wp = rp(Rp, void 0, void 0, { sqrt: Up }), Gp = Lp({
	a: BigInt(0),
	b: BigInt(7),
	Fp: Wp,
	n: zp,
	Gx: BigInt("55066263022277343669578718895168534326250603453777594175500187360389116729240"),
	Gy: BigInt("32670510020758816978083085130507043184471273380659243275938904335757337482424"),
	h: BigInt(1),
	lowS: !0,
	endo: {
		beta: BigInt("0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee"),
		splitScalar: (e) => {
			let t = zp, n = BigInt("0x3086d221a7d46bcde86c90e49284eb15"), r = -Bp * BigInt("0xe4437ed6010e88286f547fa90abfe4c3"), i = BigInt("0x114ca50f7a8e2f3f657c1108d9d44cfd8"), a = n, o = BigInt("0x100000000000000000000000000000000"), s = Hp(a * e, t), c = Hp(-r * e, t), l = Kf(e - s * n - c * i, t), u = Kf(-s * r - c * a, t), d = l > o, f = u > o;
			if (d && (l = t - l), f && (u = t - u), l > o || u > o) throw Error("splitScalar: Endomorphism failed, k=" + e);
			return {
				k1neg: d,
				k1: l,
				k2neg: f,
				k2: u
			};
		}
	}
}, Pd);
Gp.ProjectivePoint, Gp.utils.randomPrivateKey;
var Kp = Pp(Wp, [
	[
		"0x8e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38daaaaa8c7",
		"0x7d3d4c80bc321d5b9f315cea7fd44c5d595d2fc0bf63b92dfff1044f17c6581",
		"0x534c328d23f234e6e2a413deca25caece4506144037c40314ecbd0b53d9dd262",
		"0x8e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38e38daaaaa88c"
	],
	[
		"0xd35771193d94918a9ca34ccbb7b640dd86cd409542f8487d9fe6b745781eb49b",
		"0xedadc6f64383dc1df7c4b2d51b54225406d36b641f5e41bbc52a56612a8c6d14",
		"0x0000000000000000000000000000000000000000000000000000000000000001"
	],
	[
		"0x4bda12f684bda12f684bda12f684bda12f684bda12f684bda12f684b8e38e23c",
		"0xc75e0c32d5cb7c0fa9d0a54b12a0a6d5647ab046d686da6fdffc90fc201d71a3",
		"0x29a6194691f91a73715209ef6512e576722830a201be2018a765e85a9ecee931",
		"0x2f684bda12f684bda12f684bda12f684bda12f684bda12f684bda12f38e38d84"
	],
	[
		"0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffff93b",
		"0x7a06534bb8bdb49fd5e9e6632722c2989467c1bfc8e8d978dfb425d2685c2573",
		"0x6484aa716545ca2cf3a70c3fa8fe337e0a3d21162f0d6299a7bf8192bfd2a76f",
		"0x0000000000000000000000000000000000000000000000000000000000000001"
	]
].map((e) => e.map((e) => BigInt(e)))), qp = wp(Wp, {
	A: BigInt("0x3f8731abdd661adca08a5558f0f5d272e953d363cb6f0e5d405447c01a444533"),
	B: BigInt("1771"),
	Z: Wp.create(BigInt("-11"))
}), Jp = Fp(Gp.ProjectivePoint, (e) => {
	let { x: t, y: n } = qp(Wp.create(e[0]));
	return Kp(t, n);
}, {
	DST: "secp256k1_XMD:SHA-256_SSWU_RO_",
	encodeDST: "secp256k1_XMD:SHA-256_SSWU_NU_",
	p: Wp.ORDER,
	m: 1,
	k: 128,
	expand: "xmd",
	hash: Pd
});
Jp.hashToCurve, Jp.encodeToCurve;
//#endregion
//#region node_modules/ethers/lib.esm/constants/hashes.js
var Yp = "0x0000000000000000000000000000000000000000000000000000000000000000", Xp = "Ethereum Signed Message:\n", Zp = BigInt(0), Qp = BigInt(1), $p = BigInt(2), em = BigInt(27), tm = BigInt(28), nm = BigInt(35), rm = BigInt("0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"), im = rm / $p, am = Symbol.for("nodejs.util.inspect.custom"), om = {};
function sm(e) {
	return Xu(rd(e), 32);
}
var cm = class e {
	#e;
	#t;
	#n;
	#r;
	get r() {
		return this.#e;
	}
	set r(e) {
		$(Ju(e) === 32, "invalid r", "value", e), this.#e = Ku(e);
	}
	get s() {
		return $(parseInt(this.#t.substring(0, 3)) < 8, "non-canonical s; use ._s", "s", this.#t), this.#t;
	}
	set s(e) {
		$(Ju(e) === 32, "invalid s", "value", e), this.#t = Ku(e);
	}
	get _s() {
		return this.#t;
	}
	isValid() {
		return BigInt(this.#t) <= im;
	}
	get v() {
		return this.#n;
	}
	set v(e) {
		let t = td(e, "value");
		$(t === 27 || t === 28, "invalid v", "v", e), this.#n = t;
	}
	get networkV() {
		return this.#r;
	}
	get legacyChainId() {
		let t = this.networkV;
		return t == null ? null : e.getChainId(t);
	}
	get yParity() {
		return this.v === 27 ? 0 : 1;
	}
	get yParityAndS() {
		let e = Hu(this.s);
		return this.yParity && (e[0] |= 128), Ku(e);
	}
	get compactSerialized() {
		return qu([this.r, this.yParityAndS]);
	}
	get serialized() {
		return qu([
			this.r,
			this.s,
			this.yParity ? "0x1c" : "0x1b"
		]);
	}
	constructor(e, t, n, r) {
		Bu(e, om, "Signature"), this.#e = t, this.#t = n, this.#n = r, this.#r = null;
	}
	getCanonical() {
		if (this.isValid()) return this;
		let t = rm - BigInt(this._s), n = 55 - this.v, r = new e(om, this.r, sm(t), n);
		return this.networkV && (r.#r = this.networkV), r;
	}
	clone() {
		let t = new e(om, this.r, this._s, this.v);
		return this.networkV && (t.#r = this.networkV), t;
	}
	toJSON() {
		let e = this.networkV;
		return {
			_type: "signature",
			networkV: e == null ? null : e.toString(),
			r: this.r,
			s: this._s,
			v: this.v
		};
	}
	[am]() {
		return this.toString();
	}
	toString() {
		return this.isValid() ? `Signature { r: ${this.r}, s: ${this._s}, v: ${this.v} }` : `Signature { r: ${this.r}, s: ${this._s}, v: ${this.v}, valid: false }`;
	}
	static getChainId(e) {
		let t = $u(e, "v");
		return t == em || t == tm ? Zp : ($(t >= nm, "invalid EIP-155 v", "v", e), (t - nm) / $p);
	}
	static getChainIdV(e, t) {
		return $u(e) * $p + BigInt(35 + t - 27);
	}
	static getNormalizedV(e) {
		let t = $u(e);
		return t === Zp || t === em ? 27 : t === Qp || t === tm ? 28 : ($(t >= nm, "invalid v", "v", e), t & Qp ? 27 : 28);
	}
	static from(t) {
		function n(e, n) {
			$(e, n, "signature", t);
		}
		if (t == null) return new e(om, Yp, Yp, 27);
		if (typeof t == "string") {
			let r = Hu(t, "signature");
			if (r.length === 64) {
				let t = Ku(r.slice(0, 32)), n = r.slice(32, 64), i = n[0] & 128 ? 28 : 27;
				return n[0] &= 127, new e(om, t, Ku(n), i);
			}
			if (r.length === 65) return new e(om, Ku(r.slice(0, 32)), Ku(r.slice(32, 64)), e.getNormalizedV(r[64]));
			n(!1, "invalid raw signature length");
		}
		if (t instanceof e) return t.clone();
		let r = t.r;
		n(r != null, "missing r");
		let i = sm(r), a = (function(e, t) {
			if (e != null) return sm(e);
			if (t != null) {
				n(Wu(t, 32), "invalid yParityAndS");
				let e = Hu(t);
				return e[0] &= 127, Ku(e);
			}
			n(!1, "missing s");
		})(t.s, t.yParityAndS), { networkV: o, v: s } = (function(t, r, i) {
			if (t != null) {
				let n = $u(t);
				return {
					networkV: n >= nm ? n : void 0,
					v: e.getNormalizedV(n)
				};
			}
			if (r != null) return n(Wu(r, 32), "invalid yParityAndS"), { v: Hu(r)[0] & 128 ? 28 : 27 };
			if (i != null) {
				switch (td(i, "sig.yParity")) {
					case 0: return { v: 27 };
					case 1: return { v: 28 };
				}
				n(!1, "invalid yParity");
			}
			n(!1, "missing v");
		})(t.v, t.yParityAndS, t.yParity), c = new e(om, i, a, s);
		return o && (c.#r = o), n(t.yParity == null || td(t.yParity, "sig.yParity") === c.yParity, "yParity mismatch"), n(t.yParityAndS == null || t.yParityAndS === c.yParityAndS, "yParityAndS mismatch"), c;
	}
}, lm = class e {
	#e;
	constructor(e) {
		$(Ju(e) === 32, "invalid private key", "privateKey", "[REDACTED]"), this.#e = Ku(e);
	}
	get privateKey() {
		return this.#e;
	}
	get publicKey() {
		return e.computePublicKey(this.#e);
	}
	get compressedPublicKey() {
		return e.computePublicKey(this.#e, !0);
	}
	sign(e) {
		$(Ju(e) === 32, "invalid digest length", "digest", e);
		let t = Gp.sign(Uu(e), Uu(this.#e), { lowS: !0 });
		return cm.from({
			r: nd(t.r, 32),
			s: nd(t.s, 32),
			v: t.recovery ? 28 : 27
		});
	}
	computeSharedSecret(t) {
		let n = e.computePublicKey(t);
		return Ku(Gp.getSharedSecret(Uu(this.#e), Hu(n), !1));
	}
	static computePublicKey(e, t) {
		let n = Hu(e, "key");
		if (n.length === 32) return Ku(Gp.getPublicKey(n, !!t));
		if (n.length === 64) {
			let e = new Uint8Array(65);
			e[0] = 4, e.set(n, 1), n = e;
		}
		return Ku(Gp.ProjectivePoint.fromHex(n).toRawBytes(t));
	}
	static recoverPublicKey(e, t) {
		$(Ju(e) === 32, "invalid digest length", "digest", e);
		let n = cm.from(t), r = Gp.Signature.fromCompact(Uu(qu([n.r, n.s])));
		r = r.addRecoveryBit(n.yParity);
		let i = r.recoverPublicKey(Uu(e));
		return $(i != null, "invalid signature for digest", "signature", t), "0x" + i.toHex(!1);
	}
	static addPoints(t, n, r) {
		let i = Gp.ProjectivePoint.fromHex(e.computePublicKey(t).substring(2)), a = Gp.ProjectivePoint.fromHex(e.computePublicKey(n).substring(2));
		return "0x" + i.add(a).toHex(!!r);
	}
}, um = BigInt(0), dm = BigInt(36);
function fm(e) {
	e = e.toLowerCase();
	let t = e.substring(2).split(""), n = new Uint8Array(40);
	for (let e = 0; e < 40; e++) n[e] = t[e].charCodeAt(0);
	let r = Hu(lf(n));
	for (let e = 0; e < 40; e += 2) r[e >> 1] >> 4 >= 8 && (t[e] = t[e].toUpperCase()), (r[e >> 1] & 15) >= 8 && (t[e + 1] = t[e + 1].toUpperCase());
	return "0x" + t.join("");
}
var pm = {};
for (let e = 0; e < 10; e++) pm[String(e)] = String(e);
for (let e = 0; e < 26; e++) pm[String.fromCharCode(65 + e)] = String(10 + e);
var mm = 15;
function hm(e) {
	e = e.toUpperCase(), e = e.substring(4) + e.substring(0, 2) + "00";
	let t = e.split("").map((e) => pm[e]).join("");
	for (; t.length >= mm;) {
		let e = t.substring(0, mm);
		t = parseInt(e, 10) % 97 + t.substring(e.length);
	}
	let n = String(98 - parseInt(t, 10) % 97);
	for (; n.length < 2;) n = "0" + n;
	return n;
}
var gm = (function() {
	let e = {};
	for (let t = 0; t < 36; t++) {
		let n = "0123456789abcdefghijklmnopqrstuvwxyz"[t];
		e[n] = BigInt(t);
	}
	return e;
})();
function _m(e) {
	e = e.toLowerCase();
	let t = um;
	for (let n = 0; n < e.length; n++) t = t * dm + gm[e[n]];
	return t;
}
function vm(e) {
	if ($(typeof e == "string", "invalid address", "address", e), e.match(/^(0x)?[0-9a-fA-F]{40}$/)) {
		e.startsWith("0x") || (e = "0x" + e);
		let t = fm(e);
		return $(!e.match(/([A-F].*[a-f])|([a-f].*[A-F])/) || t === e, "bad address checksum", "address", e), t;
	}
	if (e.match(/^XE[0-9]{2}[0-9A-Za-z]{30,31}$/)) {
		$(e.substring(2, 4) === hm(e), "bad icap checksum", "address", e);
		let t = _m(e.substring(4)).toString(16);
		for (; t.length < 40;) t = "0" + t;
		return fm("0x" + t);
	}
	$(!1, "invalid address", "address", e);
}
//#endregion
//#region node_modules/ethers/lib.esm/transaction/address.js
function ym(e) {
	let t;
	return t = typeof e == "string" ? lm.computePublicKey(e, !1) : e.publicKey, vm(lf("0x" + t.substring(4)).substring(26));
}
function bm(e, t) {
	return ym(lm.recoverPublicKey(e, t));
}
//#endregion
//#region node_modules/ethers/lib.esm/hash/message.js
function xm(e) {
	return typeof e == "string" && (e = sd(e)), lf(qu([
		sd(Xp),
		sd(String(e.length)),
		e
	]));
}
function Sm(e, t) {
	return bm(xm(e), t);
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/evm/verify.js
function Cm(e, t, n) {
	return n.toLowerCase() === Sm(typeof e == "string" ? e : y(e), t).toLowerCase();
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/nostr/verify.js
function wm(e) {
	if (typeof e == "string") try {
		let t = JSON.parse(e);
		if (typeof t == "object" && typeof t.created_at == "number" && typeof t.kind == "number" && typeof t.content == "string" && Array.isArray(t.tags) && t.tags.every((e) => Array.isArray(e) && e.every((e) => typeof e == "string"))) return t;
	} catch {}
	return {
		kind: 23335,
		created_at: 0,
		content: typeof e == "string" ? e : K(e),
		tags: []
	};
}
function Tm(e) {
	return Sr(y(JSON.stringify([
		0,
		e.pubkey,
		e.created_at,
		e.kind,
		e.tags,
		e.content
	]), "utf8"));
}
function Em(e, t, n) {
	let { words: r } = ur.bech32.decode(n), i = K(ur.bech32.fromWords(r)).slice(2), a = Tm({
		...wm(e),
		pubkey: i
	});
	try {
		return Ia.verify(K(t).slice(2), a, i);
	} catch {
		return !1;
	}
}
//#endregion
//#region node_modules/@ckb-ccc/core/dist/signer/signer/index.js
var Dm;
(function(e) {
	e.Unknown = "Unknown", e.BtcEcdsa = "BtcEcdsa", e.EvmPersonal = "EvmPersonal", e.JoyId = "JoyId", e.NostrEvent = "NostrEvent", e.CkbSecp256k1 = "CkbSecp256k1", e.DogeEcdsa = "DogeEcdsa";
})(Dm ||= {});
var Om;
(function(e) {
	e.EVM = "EVM", e.BTC = "BTC", e.CKB = "CKB", e.Nostr = "Nostr", e.Doge = "Doge";
})(Om ||= {});
var km = class e {
	constructor(e) {
		this.client_ = e;
	}
	get client() {
		return this.client_;
	}
	matchNetworkPreference(e, t) {
		if (!(t !== void 0 && e.some(({ signerType: e, addressPrefix: n, network: r }) => e === this.type && n === this.client.addressPrefix && r === t))) return e.find(({ signerType: e, addressPrefix: t }) => e === this.type && t === this.client.addressPrefix);
	}
	static async verifyMessage(e, t) {
		switch (t.signType) {
			case Dm.EvmPersonal: return Cm(e, t.signature, t.identity);
			case Dm.BtcEcdsa: return fo(e, t.signature, t.identity);
			case Dm.JoyId: return ku(e, t.signature, t.identity);
			case Dm.NostrEvent: return Em(e, t.signature, t.identity);
			case Dm.CkbSecp256k1: return mo(e, t.signature, t.identity);
			case Dm.DogeEcdsa: return ju(e, t.signature, t.identity);
			case Dm.Unknown: throw Error("Unknown signer sign type");
		}
	}
	onReplaced(e) {
		return () => {};
	}
	async disconnect() {}
	async getIdentity() {
		return this.getInternalAddress();
	}
	async getRecommendedAddressObj(e) {
		return (await this.getAddressObjs())[0];
	}
	async getRecommendedAddress(e) {
		return (await this.getRecommendedAddressObj(e)).toString();
	}
	async getAddresses() {
		return this.getAddressObjs().then((e) => e.map((e) => e.toString()));
	}
	async *findCellsOnChain(e, t, n, r) {
		let i = await this.getAddressObjs();
		for (let { script: a } of i) for await (let i of this.client.findCellsOnChain({
			script: a,
			scriptType: "lock",
			filter: e,
			scriptSearchMode: "exact",
			withData: t
		}, n, r)) yield i;
	}
	async *findCells(e, t, n, r) {
		let i = await this.getAddressObjs();
		for (let { script: a } of i) for await (let i of this.client.findCells({
			script: a,
			scriptType: "lock",
			filter: e,
			scriptSearchMode: "exact",
			withData: t
		}, n, r)) yield i;
	}
	async *findTransactions(e, t, n, r) {
		let i = await this.getAddressObjs();
		for (let { script: a } of i) for await (let i of this.client.findTransactions({
			script: a,
			scriptType: "lock",
			filter: e,
			scriptSearchMode: "exact",
			groupByTransaction: t
		}, n, r)) yield i;
	}
	async getBalance() {
		return this.client.getBalance((await this.getAddressObjs()).map(({ script: e }) => e));
	}
	async signMessage(e) {
		return {
			signature: await this.signMessageRaw(e),
			identity: await this.getIdentity(),
			signType: this.signType
		};
	}
	signMessageRaw(e) {
		throw Error("Signer.signMessageRaw not implemented");
	}
	async verifyMessage(t, n) {
		return typeof n == "string" ? e.verifyMessage(t, {
			signType: this.signType,
			signature: n,
			identity: await this.getIdentity()
		}) : n.identity !== await this.getIdentity() || ![Dm.Unknown, this.signType].includes(n.signType) ? !1 : e.verifyMessage(t, n);
	}
	async sendTransaction(e) {
		return this.client.sendTransaction(await this.signTransaction(e));
	}
	async signTransaction(e) {
		let t = await this.prepareTransaction(e);
		return this.signOnlyTransaction(t);
	}
	async prepareTransaction(e) {
		return cr.from(e);
	}
	signOnlyTransaction(e) {
		throw Error("Signer.signOnlyTransaction not implemented");
	}
};
//#endregion
//#region node_modules/@ckb-ccc/joy-id/dist/common/index.js
async function Am(e, t) {
	return t.popup == null && (t.popup = Lo(""), t.popup == null) ? Wo(async () => Am(e, t)) : (t.popup.location.href = e, new Promise((e, n) => {
		To() && n(new Po(t.popup));
		let r, i, a = setInterval(() => {
			t.popup?.closed && (clearInterval(a), clearTimeout(i), window.removeEventListener("message", r, !1), n(new No(t.popup)));
		}, 1e3);
		i = setTimeout(() => {
			clearInterval(a), n(new Mo(t.popup)), window.removeEventListener("message", r, !1);
		}, (t.timeoutInSeconds ?? 3e3) * 1e3), r = (o) => {
			let { joyidAppURL: s } = t, c = new URL(s);
			o.origin === c.origin && (!o.data || o.data?.type !== t.type || (clearTimeout(i), clearInterval(a), window.removeEventListener("message", r, !1), t.popup.close(), o.data.error && n(Error(o.data.error)), e(o.data.data)));
		}, window.addEventListener("message", r);
	}));
}
//#endregion
//#region node_modules/@ckb-ccc/joy-id/dist/connectionsStorage/index.js
function jm(e, t) {
	return e.uri === t.uri && e.addressType.startsWith(t.addressType);
}
var Mm = class {
	constructor(e = "ccc-joy-id-signer") {
		this.storageKey = e, this.operationLock = Promise.resolve();
	}
	async readConnections() {
		return JSON.parse(window.localStorage.getItem(this.storageKey) ?? "[]");
	}
	async get(e) {
		return (await this.readConnections()).find(([t]) => jm(e, t))?.[1];
	}
	async set(e, t) {
		let n = this.operationLock.catch(() => void 0).then(async () => {
			let n = await this.readConnections();
			if (t) {
				let r = n.find(([t]) => jm(t, e));
				r ? r[1] = t : n.push([e, t]), window.localStorage.setItem(this.storageKey, JSON.stringify(n));
			} else window.localStorage.setItem(this.storageKey, JSON.stringify(n.filter(([t]) => !jm(t, e))));
		});
		this.operationLock = n, await n;
	}
}, Nm = class extends km {
	get type() {
		return Om.CKB;
	}
	get signType() {
		return Dm.JoyId;
	}
	async assertConnection() {
		if (!await this.isConnected() || !this.connection) throw Error("Not connected");
		return this.connection;
	}
	constructor(e, t, n, r, i, a = new Mm()) {
		super(e), this.name = t, this.icon = n, this._appUri = r, this._aggregatorUri = i, this.connectionsRepo = a;
	}
	getConfig() {
		return {
			redirectURL: location.href,
			joyidAppURL: this._appUri ?? (this.client.addressPrefix === "ckb" ? "https://app.joy.id" : "https://testnet.joyid.dev"),
			name: this.name,
			logo: this.icon
		};
	}
	getAggregatorUri() {
		return this._aggregatorUri ?? (this.client.addressPrefix === "ckb" ? "https://cota.nervina.dev/mainnet-aggregator" : "https://cota.nervina.dev/aggregator");
	}
	async connect() {
		let e = this.getConfig(), t = await Am(Io(e, "popup", "/auth"), {
			...e,
			type: Do.Auth
		});
		this.connection = {
			address: t.address,
			publicKey: K(t.pubkey),
			keyType: t.keyType
		}, await this.saveConnection();
	}
	async disconnect() {
		await super.disconnect(), this.connection = void 0, await this.saveConnection();
	}
	async isConnected() {
		return this.connection ? !0 : (await this.restoreConnection(), this.connection !== void 0);
	}
	async getInternalAddress() {
		return (await this.assertConnection()).address;
	}
	async getIdentity() {
		let e = await this.assertConnection();
		return JSON.stringify({
			keyType: e.keyType,
			publicKey: e.publicKey.slice(2)
		});
	}
	async getAddressObj() {
		return await hr.fromString(await this.getInternalAddress(), this.client);
	}
	async getAddressObjs() {
		return [await this.getAddressObj()];
	}
	async prepareTransaction(e) {
		let t = cr.from(e);
		await t.addCellDepsOfKnownScripts(this.client, Y.JoyId);
		let n = await t.findInputIndexByLock((await this.getAddressObj()).script, this.client);
		if (n === void 0) return t;
		let r = t.getWitnessArgsAt(n) ?? ar.from({});
		return r.lock = K("00".repeat(1e3)), await this.prepareTransactionForSubKey(t, r), t.setWitnessArgsAt(n, r), t;
	}
	async prepareTransactionForSubKey(e, t) {
		if (this.connection?.keyType !== "sub_key" || (t.outputType ?? "0x") !== "0x") return;
		let n = Pe(this.connection.publicKey).substring(0, 42), r = (await this.getAddressObj()).script, { unlock_entry: i } = await new mu(this.getAggregatorUri()).generateSubkeyUnlockSmt({
			alg_index: 1,
			pubkey_hash: n,
			lock_script: K(r.toBytes())
		});
		t.outputType = K(i);
		let a = [];
		for await (let e of this.client.findCellsByLock(r, await X.fromKnownScript(this.client, Y.COTA, "0x"))) a.push(rr.from({
			depType: "code",
			outPoint: e.outPoint
		}));
		if (a.length === 0) throw Error("No COTA cells for sub key wallet");
		e.addCellDepsAtStart(a);
	}
	async signOnlyTransaction(e) {
		let t = cr.from(e), { script: n } = await this.getAddressObj(), r = await qe(t.inputs, async (e, t, r) => {
			let { cellOutput: i } = await t.getCell(this.client);
			i.lock.eq(n) && e.push(r);
		}, []);
		await t.prepareSighashAllWitness(n, 0, this.client), t.inputs.forEach((e) => {
			e.cellOutput = void 0, e.outputData = void 0;
		});
		let i = this.getConfig(), a = await Am(Io({
			...i,
			tx: JSON.parse(t.stringify()),
			signerAddress: (await this.assertConnection()).address,
			witnessIndexes: r
		}, "popup", "/sign-ckb-raw-tx"), {
			...i,
			type: Do.SignCkbRawTx
		});
		return cr.from(a.tx);
	}
	async signMessageRaw(e) {
		let { address: t } = await this.assertConnection(), n = typeof e == "string" ? e : K(e).slice(2), r = this.getConfig(), i = await Am(Io({
			...r,
			challenge: n,
			isData: typeof e != "string",
			address: t
		}, "popup", "/sign-message"), {
			...r,
			type: Do.SignMessage
		});
		return JSON.stringify({
			signature: i.signature,
			alg: i.alg,
			message: i.message
		});
	}
	async saveConnection() {
		return this.connectionsRepo.set({
			uri: this.getConfig().joyidAppURL,
			addressType: "ckb"
		}, this.connection);
	}
	async restoreConnection() {
		this.connection = await this.connectionsRepo.get({
			uri: this.getConfig().joyidAppURL,
			addressType: "ckb"
		});
	}
}, Pm = 1, Fm = "JIDSDR", Im = "https://cryptologos.cc/logos/nervos-network-ckb-logo.png", Lm = {
	theme: "dark",
	lang: "en",
	notifications: !0,
	fontSize: "medium"
};
//#endregion
//#region src/settings.js
function Rm(e) {
	let t = JSON.stringify(e), n = new TextEncoder().encode(t), r = new Uint8Array(1 + n.length);
	return r[0] = 1, r.set(n, 1), r;
}
function zm(e) {
	let t;
	if (typeof e == "string") {
		let n = e.startsWith("0x") ? e.slice(2) : e;
		t = new Uint8Array(n.match(/.{2}/g).map((e) => parseInt(e, 16)));
	} else t = new Uint8Array(e);
	if (t.length < 2 || t[0] !== 1) return null;
	let n = new TextDecoder().decode(t.slice(1));
	try {
		return JSON.parse(n);
	} catch {
		return null;
	}
}
function Bm(e, t) {
	return {
		...Lm,
		...e,
		...t
	};
}
function Vm(e) {
	return "0x" + Array.from(e).map((e) => e.toString(16).padStart(2, "0")).join("");
}
//#endregion
//#region src/ckb.js
var Hm = null, Um = null;
function Wm() {
	return Hm ||= new It(), Hm;
}
function Gm() {
	return Um ||= new Nm(Wm(), Fm, Im), Um;
}
async function Km() {
	let e = Gm();
	return await e.connect(), {
		address: await e.getInternalAddress(),
		lockScript: (await e.getAddressObj()).script
	};
}
async function qm() {
	await Gm().disconnect();
}
async function Jm() {
	return Gm().isConnected();
}
async function Ym() {
	let e = (await Gm().getAddressObj()).script, t = Wm().findCellsByLock(e, null, !0);
	for await (let e of t) {
		let t = e.outputData;
		if (!t || t === "0x") continue;
		let n = zm(t);
		if (n) return {
			cell: e,
			settings: n
		};
	}
	return null;
}
async function Xm(e, t, n) {
	let r = Gm(), i = (await r.getAddressObj()).script, a = Rm(e), o = Vm(a), s = i.toBytes().length, c = a.length, l = 8 + s + c, u = BigInt(l) * 100000000n;
	n("Building transaction...");
	let d = cr.from({
		outputs: [{
			lock: i,
			capacity: u
		}],
		outputsData: [o]
	});
	t && d.inputs.push(tr.from({ previousOutput: t.outPoint })), n("Completing fees..."), await d.completeFeeBy(r), n("Signing with JoyID...");
	let f = await r.signTransaction(d);
	n("Broadcasting...");
	let p = await Wm().sendTransaction(f);
	return n(`Confirmed: ${p}`), p;
}
async function Zm() {
	let e = await Gm().getBalance();
	return (Number(e) / 1e8).toFixed(2);
}
//#endregion
export { Fm as APP_NAME, Lm as DEFAULT_SETTINGS, Pm as SETTINGS_VERSION, Vm as bytesToHex, Km as connect, zm as decodeSettings, qm as disconnect, Rm as encodeSettings, Ym as findSettingsCell, Zm as getBalance, Wm as getClient, Gm as getSigner, Jm as isConnected, Bm as mergeSettings, Xm as saveSettings };
