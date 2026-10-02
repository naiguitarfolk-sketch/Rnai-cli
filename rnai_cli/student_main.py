# -*- coding: utf-8 -*-
"""Entry point for rnai-student CLI executable"""
from __future__ import annotations

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from . import config, research_models as rmodels, research_tools as rtools
from .student_ui import serve_student

app = typer.Typer(help="Rnai Student Edition — ระบบผู้ช่วยกำกับกระบวนการเรียนรู้ มสธ. สำหรับงานวิจัย")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    port: int = typer.Option(8766, "--port", "-p", help="พอร์ต HTTP Server สำหรับผู้เรียน"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="IP address ที่ฟัง (default 0.0.0.0)"),
    no_browser: bool = typer.Option(False, "--no-browser", help="ไม่เปิดเบราว์เซอร์อัตโนมัติ"),
):
    """เปิดระบบผู้ช่วยกำกับกระบวนการเรียนรู้ มสธ. สำหรับนักศึกษา"""
    if ctx.invoked_subcommand is None:
        serve_student(port=port, host=host, open_browser=not no_browser)


@app.command()
def week(
    num: int = typer.Argument(..., help="ระบุสัปดาห์การวิจัย (1-12)"),
    fading: Optional[str] = typer.Option(None, "--fading", "-f", help="ระดับการช่วยเหลือ (L1, L2, L3, L4)"),
):
    """ตั้งค่าสัปดาห์การวิจัยและระดับการถอนความช่วยเหลือ (Fading Scaffolding)"""
    rtools.set_week(num, fading_level=fading or "")
    st = rtools.load_state()
    console.print(f"[green]✓ ตั้งค่าสัปดาห์การวิจัยเป็น สัปดาห์ที่ {st['week']} (ระดับการช่วยเหลือ {st['fading_level']}) เรียบร้อยแล้ว[/green]")


@app.command()
def models(
    use: Optional[str] = typer.Option(None, "--use", "-u", help="เปลี่ยนโมเดลที่ใช้ (base | v3 | tutor-v1 | v4.1)"),
):
    """แสดงทะเบียนโมเดลวิจัย และเลือกว่าจะใช้ตัวไหน"""
    if use:
        try:
            m = rmodels.get(use)
        except KeyError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        if not m.evaluated:
            console.print(
                f"[yellow]⚠️  {m.label} ยังไม่เคยผ่านการประเมิน 30 สถานการณ์[/yellow]\n"
                "[yellow]   ใช้ทดลองได้ แต่ห้ามใช้เก็บข้อมูลวิจัย — rnai-student จะปฏิเสธการให้บริการ[/yellow]"
            )
        config.set_value("RESEARCH_MODEL", m.key)
        console.print(f"[green]✓ เปลี่ยนไปใช้ {m.label} ({m.ollama_name})[/green]")
        return

    current = config.get("RESEARCH_MODEL") or rmodels.DEFAULT_KEY
    table = Table(title="ทะเบียนโมเดลวิจัย")
    table.add_column("", width=2)
    table.add_column("key", style="cyan")
    table.add_column("ชื่อใน Ollama")
    table.add_column("ประเมินแล้ว", justify="center")

    for key in sorted(rmodels.MODELS):
        m = rmodels.MODELS[key]
        table.add_row(
            "▶" if key == current else "",
            key,
            m.ollama_name,
            "[green]✅[/green]" if m.evaluated else "[red]🔴 ยัง[/red]",
        )
    console.print(table)

    m = rmodels.get(current)
    console.print(f"\n[bold]กำลังใช้:[/bold] {m.label}")
    if m.note:
        console.print(f"[dim]{m.note}[/dim]")
    opts = " · ".join(f"{k}={v}" for k, v in m.options.items())
    console.print(f"[dim]ค่าการสุ่ม (ตรงกับตอนประเมิน): {opts}[/dim]")


@app.command()
def report():
    """แสดงรายงานสถิติการใช้งานและการถอนความช่วยเหลือของผู้เรียน (สำหรับบทที่ 4)"""
    rep = rtools.fading_report()
    table = Table(title=f"สรุปรายงานวิจัย (รวมทั้งสิ้น {rep.get('total', 0)} ครั้ง)")
    table.add_column("ระดับ Fading", style="cyan")
    table.add_column("จำนวนการเรียก", justify="right")
    table.add_column("ผ่านด่าน (Accepted)", justify="right", style="green")
    table.add_column("ถูกปฏิเสธ (Denied)", justify="right", style="red")

    by_lvl = rep.get("by_fading_level", {})
    if not by_lvl:
        console.print("[dim]ยังไม่มีข้อมูลการใช้งานของผู้เรียน[/dim]")
        return

    for lvl, data in sorted(by_lvl.items()):
        table.add_row(lvl, str(data["calls"]), str(data["accepted"]), str(data["denied"]))

    console.print(table)


if __name__ == "__main__":
    app()
