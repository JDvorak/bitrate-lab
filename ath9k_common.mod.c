#include <linux/module.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

MODULE_INFO(vermagic, VERMAGIC_STRING);

struct module __this_module
__attribute__((section(".gnu.linkonce.this_module"))) = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};

MODULE_INFO(intree, "Y");

static const struct modversion_info ____versions[]
__used
__attribute__((section("__versions"))) = {
	{ 0x915a5725, "module_layout" },
	{ 0xb4390f9a, "mcount" },
	{ 0xab5613f9, "ath_hw_keyreset" },
	{ 0x497f5f6e, "ath9k_hw_set_txpowerlimit" },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=ath,ath9k_hw";

