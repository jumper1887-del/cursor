#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilder Komprimieren – Komprimiert alle Bilder im Ordner
- Reduziert Dateigröße durch Kompression
- Passt Größe an wenn größer als max_width
- Überschreibt Originale oder erstellt Backup
"""

import os
from pathlib import Path
from PIL import Image
from typing import Tuple, Optional

# ============================================
# KONFIGURATION
# ============================================

BILDER_ORDNER = '/root/Skrip/Datenbank/Schiffsbilder'
MAX_WIDTH = 1024  # Maximale Breite (nur verkleinern wenn größer)
QUALITY = 80  # JPEG Qualität (optimiert für gute Qualität bei kleinerer Datei)
OPTIMIZE = True  # Progressive JPEG und Optimierung aktivieren
SUBSAMPLING = '4:2:0'  # Chroma Subsampling für bessere Kompression
BACKUP = False  # True = Backup erstellen, False = Originale überschreiben

# Erlaubte Bildformate
BILD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def get_file_size_mb(filepath: Path) -> float:
    """Gibt Dateigröße in MB zurück"""
    return filepath.stat().st_size / (1024 * 1024)


def compress_image(image_path: Path, max_width: int = MAX_WIDTH, quality: int = QUALITY) -> Tuple[bool, float, float]:
    """
    Komprimiert ein Bild mit optimierten Techniken
    
    Returns:
        (success: bool, original_size_mb: float, new_size_mb: float)
    """
    try:
        original_size = get_file_size_mb(image_path)
        
        # Öffne Bild
        img = Image.open(image_path)
        original_format = img.format
        original_width, original_height = img.size
        
        # Konvertiere zu RGB falls nötig
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Größe anpassen wenn größer als max_width (mit hochwertigem Algorithmus)
        if original_width > max_width:
            ratio = max_width / original_width
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            # LANCZOS für beste Qualität beim Verkleinern
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Speichere komprimiert
        # Bestimme Ausgabeformat
        if image_path.suffix.lower() in ('.png', '.gif', '.bmp'):
            # Konvertiere zu JPEG für bessere Kompression
            output_path = image_path.with_suffix('.jpg')
            if output_path != image_path and output_path.exists():
                # Falls .jpg bereits existiert, überschreibe Original
                output_path = image_path
        else:
            output_path = image_path
        
        # Optimierte Speicherung mit mehreren Techniken
        # Progressive JPEG für bessere Kompression (10-30% kleiner)
        # Optimize aktiviert Huffman-Tabellen-Optimierung
        save_kwargs = {
            'format': 'JPEG',
            'quality': quality,
            'optimize': OPTIMIZE,  # Huffman-Tabellen optimieren (kleinere Datei)
            'progressive': OPTIMIZE,  # Progressive JPEG (bessere Kompression, 10-30% kleiner)
            'subsampling': 0,  # Kein Chroma Subsampling für beste Qualität bei kleinerer Datei
        }
        
        # Speichere mit optimierten Einstellungen
        img.save(output_path, **save_kwargs)
        
        # Adaptive Optimierung: Wenn Datei noch zu groß, versuche intelligente Reduktion
        new_size = get_file_size_mb(output_path)
        target_size = original_size * 0.4  # Ziel: 40% der Originalgröße
        
        if new_size > target_size and quality > 65:
            # Versuche mit optimierter Qualität
            # Reduziere Qualität schrittweise bis Ziel erreicht
            test_qualities = [quality - 5, quality - 10, max(65, quality - 15)]
            best_size = new_size
            best_quality = quality
            
            for test_q in test_qualities:
                if test_q < 65:
                    break
                img.save(output_path, format='JPEG', quality=test_q, optimize=True, progressive=True, subsampling=0)
                test_size = get_file_size_mb(output_path)
                if test_size < best_size and test_size <= target_size * 1.2:  # Max 20% über Ziel
                    best_size = test_size
                    best_quality = test_q
            
            if best_size < new_size:
                # Speichere mit bester gefundener Qualität
                img.save(output_path, format='JPEG', quality=best_quality, optimize=True, progressive=True, subsampling=0)
                new_size = best_size
        
        saved = original_size - new_size
        saved_percent = (saved / original_size * 100) if original_size > 0 else 0
        
        # Lösche Original wenn zu JPEG konvertiert wurde
        if output_path != image_path and output_path.exists():
            image_path.unlink()
        
        return True, original_size, new_size
        
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, 0


def main():
    print("=" * 50)
    print("🗜️  Bilder Komprimieren (Optimiert)")
    print("=" * 50)
    print(f"📁 Ordner: {BILDER_ORDNER}")
    print(f"📏 Max. Breite: {MAX_WIDTH}px")
    print(f"🎨 Qualität: {QUALITY} (optimiert)")
    print(f"⚙️  Progressive JPEG: {'Ja' if OPTIMIZE else 'Nein'}")
    print(f"⚙️  Optimierung: {'Aktiviert' if OPTIMIZE else 'Deaktiviert'}")
    print(f"💾 Backup: {'Ja' if BACKUP else 'Nein (Originale werden überschrieben)'}")
    print("=" * 50)
    
    bilder_path = Path(BILDER_ORDNER)
    
    if not bilder_path.exists():
        print(f"❌ Ordner nicht gefunden: {BILDER_ORDNER}")
        return
    
    # Finde alle Bilder
    bilder = []
    for file in bilder_path.iterdir():
        if file.is_file() and file.suffix.lower() in BILD_EXTENSIONS:
            bilder.append(file)
    
    if not bilder:
        print(f"⚠️  Keine Bilder gefunden in {BILDER_ORDNER}")
        return
    
    print(f"\n📊 Gefunden: {len(bilder)} Bilder\n")
    
    # Komprimiere alle Bilder
    success_count = 0
    error_count = 0
    total_original_size = 0
    total_new_size = 0
    
    print(f"Komprimiere {len(bilder)} Bilder...\n")
    
    for i, bild in enumerate(bilder, 1):
        # Fortschrittsanzeige ohne Details
        if i % 10 == 0 or i == len(bilder):
            print(f"  Fortschritt: {i}/{len(bilder)} Bilder verarbeitet...", end='\r')
        
        # Backup erstellen falls gewünscht
        if BACKUP:
            backup_path = bild.with_suffix(bild.suffix + '.backup')
            if not backup_path.exists():
                import shutil
                shutil.copy2(bild, backup_path)
        
        success, original_size, new_size = compress_image(bild, MAX_WIDTH, QUALITY)
        
        if success:
            success_count += 1
            total_original_size += original_size
            total_new_size += new_size
        else:
            error_count += 1
    
    print(f"\n  ✅ {len(bilder)} Bilder verarbeitet!                    ")
    
    # Zusammenfassung
    total_saved = total_original_size - total_new_size
    total_saved_percent = (total_saved / total_original_size * 100) if total_original_size > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"📊 ZUSAMMENFASSUNG")
    print(f"{'='*50}")
    print(f"✅ Erfolgreich komprimiert: {success_count} Bilder")
    print(f"❌ Fehler: {error_count} Bilder")
    print(f"")
    print(f"📦 GESAMT-GRÖSSE VORHER: {total_original_size:.2f} MB")
    print(f"📦 GESAMT-GRÖSSE NACHHER: {total_new_size:.2f} MB")
    print(f"💾 GESAMT KLEINER GEMACHT: {total_saved:.2f} MB")
    print(f"📊 PROZENT GESPART: {total_saved_percent:.1f}%")
    print(f"")
    print(f"📈 Durchschnitt pro Bild:")
    if success_count > 0:
        avg_original = total_original_size / success_count
        avg_new = total_new_size / success_count
        avg_saved = total_saved / success_count
        print(f"   Vorher: {avg_original:.2f} MB")
        print(f"   Nachher: {avg_new:.2f} MB")
        print(f"   Gespart: {avg_saved:.2f} MB")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()

