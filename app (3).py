# -*- coding: utf-8 -*-
"""
===============================================================================
 CONTROL DE INVENTARIO FÍSICO  |  SMITH & NEPHEW  ·  TECNITRAUMA   (versión web)
-------------------------------------------------------------------------------
 Dos perfiles:
   • PAREJAS DE CONTEO (ingresan con PIN): conteo a ciegas. Pistolean o digitan
     referencias, seleccionan/cierran seriales. NO ven cantidades del sistema,
     costos ni diferencias.
   • ADMINISTRADOR (contraseña): ve todo. Carga maestros, crea parejas, cruces,
     seriales pendientes, dashboard y reportes Excel.

 Datos: se guardan en una base de datos.
   • En línea (Streamlit Cloud + Supabase): defina DB_URL en los "Secrets".
   • Local (sin internet): se crea sola en datos_conteo/inventario.db
 Ningún registro se pierde al cerrar el navegador o recargar la página.

 Ejecutar local:  streamlit run app.py
===============================================================================
"""

import base64
import gzip
import hashlib
import io
import os
import random
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import (Column, Float, Integer, LargeBinary, MetaData, String, Table, Text, create_engine,
                        delete, insert, select, update)

st.set_page_config(
    page_title="Inventario Smith & Nephew | Tecnitrauma",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto",
)
pd.set_option("styler.render.max_elements", 5_000_000)

BODEGAS_SMITH = [58, 59, 81, 82, 83, 84]
BODEGAS_SERENA = [66, 67]
BODEGAS_EQUIPOS_CIUDAD = [2, 10, 20, 27, 33]   # bodegas de equipos de cada ciudad (por BODEGA PROPIETARIA)
ZONAS = {
    "Smith & Nephew": "SMITH",
    "Serena del Mar · Bod. 66": "SERENA",
    "Serena del Mar · Bod. 67": "SERENA",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE_DIR, "datos_conteo")
CLAVE_ADMIN_INICIAL = "Tecnitrauma2026"
TZ_COL = timezone(timedelta(hours=-5))   # hora de Colombia (el servidor en la nube usa UTC)


def ahora() -> datetime:
    return datetime.now(TZ_COL).replace(tzinfo=None)



LOGO_TECNITRAUMA_B64 = "iVBORw0KGgoAAAANSUhEUgAAARQAAABICAYAAAA3SwpBAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAAEnQAABJ0Ad5mH3gAADaMSURBVHhe7b13nBzFtf79reqevHmlVZZARAFCwhKIIEzGBpsMxoABk2xeg+HiBPja9+eI8b2AAWOT8TU4YIMkosHkDAIMEhIKKK/SarVxdvJ0V71/VPXM7EogCRaMfefRZ7Qz3dVV1RWeOnXOqSqhtdZUUUUVVQwC5MALVVRRRRUfFlVCqaKKKgYNVUKpoooqBg1VQqmiiioGDVVCqaKKKgYNVUKpoooqBg1VQqmiiioGDVVCqaKKKgYNVUKpoooqBg1VQqmiiioGDVVCqaKKKgYNVUKpoooqBg1VQqmiiioGDVVCqaKKKgYNVUKpoooqBg1VQqmiiioGDf9EQqnu61RFFf9uGFRC0QFNaFCAX3FNY64Z+BWfKrVUUcW/CwaFUAISERoEgDB/dYkyFKIfbcjSR5vgVVRRxb8BxEffU7aSEgx9gANotDbXBRqEoRQBoM03LQwJ2UBVVFHFvzgGQUIpyyGGFawsogUC3/4SqJIko0H7RmopUdlH5LQqqqjiU4FBIBQBWoDSaCQ+Gl0iiOCvj9DKkIoIJkMeCGU5qCqeVFHFvwMGYcoDKCNx+FLglPQjlfdz5o+MoBEIlNWegEYCojrjqaKKfwMMDqFojRY+ApfFvUWee2cNbekszXUJvrD7CLavDwNF0AKFixJllayyVDIIolIVVVTxT8YgEIq2elnBk8vaueqBObzXocmJCGEHJtZ6fPeY3ThiwkgryWi0dKGkbalQ1lZRRRX/0tgyoQzo7UHg0iVt9CCren3Ouu15VvRpahMJpAijFPSlk+xaW+TW/+9Qtq8NgSoanYmQNjJpTT0aZeWUsmo3SKVKOVVU8a+ArZpp6OC/kmeakUoMFQlAMnvZepanBDU1jYBEKY3AJ1ETY0Va8ubSDeZREUIL0CW3NwAPjSqrcysozlCN+b+KKqr4dGOLhKKE6ehBny5JD8IzH8syPZms9X11QJtofQFCCDwt6OvL2xgDScQ1WhQB4CAQSATSOsihRDk9bRS3VVRRxacbWyQUgUAjDEc44JdkC2E7uoliVEMtMeWBMl6xGh+hNZ5SRITPyOZaG6G2zwi0dXbTSDQShbUgC+u1YnlMVbmkiir+JbBlQtECR2sEgTRi/E3AQQtdcmrbZ8cWJg1PkO7rpIBEaxeNoDfVw4SRYabuNMQ6tRn6MJKHSUMbysIpJWpvShuulJsqqqji04ytU8oqjZLWCQ2J0MZvxBh9fXs9xML2FD9/ZB6vLE+BDiN0nn13jHPlcXuxR3OipBExxBRIN9oodhHWPV+X/GoD4sJ47ldRRRWfcmyRULTWCG0dR8wVtDZTIfsTJXwkxnLT68OcpRtp60wyvLGWqRNaSFgKUVZzMhCVGTCxKtAKLVx70zPpiZIMU0UVVXwKsRWEYqSDNT0ZOlNZdhnVTASFBoSQxjJjfuD4dl1gBRRw39ttvLayk6JSRMNhHCvhSCEIh0NIoYk4mmHxEOOHRNh1dCMtsZDNgDKkJmRVTKmiik85tkgoAEs70nzrnpd5Y0Oan5w4mQv22d6YerVrCEVY64zSKMdHIBA4pDX86ME5zHx9HQXCSAkKH6klUkujf9EKtMARGkdqRChEc63LSVNHc970Hah3NL425LVFhU8V/2Toqsbr/zi2qo8uWp/k3Y15OqKNzF+dNhe1NHpTjBQBgYlGIpCkfcVPHn6PP7/Rhqitp66+gZraBmrrEiTqanATNUQjLs0Jl4a6MPV1MeKxGAUZYd5GxS8fWczlf36b1j4PR0i0lVTwjU7H6FjKWpnydk7bBqX7x1OOrwowU97gYx2PNoHWCm231Aq+9fulKXkZaVtTClPQm4+xin9VbJWEsqQrzfl3zuaNbrhgz0Zu+PJetlN7aKlBO2jtmAV/0mg8fvjwAu5+aTW1TfUgNVJJHG3WI3fnFNO2a+DcqcNJRFxiNSHCIYdUtkhHb4H31nby93c7eG3pRg7ZvYlbzj2AUTGJVma9kBYgrHctgbkZhdg6fixBf4zjqZmmfVyxf3II3iP46yvFCy+8RGdnBxMn7skuO+9oSUEhtI8WEoFj6kQbK52pMKt4R1jroFkmakN8bPVQxSeLLRJK0OkeWbiB7/35HzTXRLjtawcxocFFU8RHIHEQSiAk5IGrH3uPP7yyCieWwBUSrR2EBKmNkqWr4DN9lMvd508lPDBBi7V9Hn96YyV3PL2Q3cfV89uzpjM8KvE1SKERRnFT2rhJbaq+2SrMnfcO11xzDVIIqxN6f5T3bxkAYbZvUNrnsMMP5+yzzhoY4l8WQfMQQtDb28vFF3+T+2fMoFDwGDVqBNdeex2nnHxiWUoFtDAk79gqMkp8TGuqJJZ+RFKllH8HbJFQVGmFjeRP/1jN9/8ymz3GjeJnJ09i8rA4YJfzSCgA//PEe/z2uVbqEvVoisbwK120cBDa+LL4wsFL93Hx4TtwyUHbmb1RNCjhIJS2zm0m1Qfnt/HNu17g+Gm7cPWpk4ij0TqQRgSgrSv/tsonBo88+ijHfPGL5ofgg2npfUtKg3RAFTnzrK9y9+9/NzDAvywqCeXee+/ltNNOo66+iVDIpbNjI/vtN51nnn6KaCxcmi9quxfo5jelKIIOmaACpArcoTcXtop/NWyxD5rR3yhPT58yhh+etC8LVrRz1q0vceOLy8no8jq/G594j9ufW06svo58McewUJG4SNORS5PSCl8ItFBIiqhYDbc+s4S/LWg3xuQKMRgtza5u2ue4PYZzxQn78tBrS7np6aWAQAjHbtRUHu0+WLZ4fziOg3QdErU11NbXU1vXQE1dAzX1DcTr6mloHkJzy3Cahg6jadhwmoYNo6ahkUR9A4mG4NNITX09AJFodGASpU75r45169YBEIlEkFISjSfo6u7A94pgCUILK3tozZo+j2W9Hst7PZb2eHRkrBmwsjiqRPJvBedHP/rRjwZerESwIRLajFKfGV1PKBTj0QXtvLSym1UbOtluTDMPvr2BW55ehkrUU8gkOXpCPT895TMcPnkMysuxoW0jGc9BhCIgFK6QZJXLWys2sOt2LYyti5YmWMbVX1g9iWRUc5wn3+vlsXnrGdkQZuKoBjNnx7eSjLErfRisXLWSxx9/nEQiQSwaJRqJEg1HiEYixOMxtNJ4ygNpZvxaK2riCRKxGOFwmFjUhI1GIoQch2nT9uNzRx4xMBmwo/yHRaVOplJq+LgRpCGEoKWlhUcf/Rtr1rSSy+UpFnKc+uVTOfbYLyKEQKFQQiKF0aN9757n+cMrq3lm3hruf2UpuWyOaTsPM4vNg6wLVarnj4qBxP1JlE8V/bHFKQ+Aths7ChyEFvgCbnh2GTc+tZS8E2Jsg0M+CxkRJZ3u43O71HPtaVNoDJUbySsrevj1k4t4aVUvsZp6IjgIIFnIMSauuOnsaUxqiaLtERxKgNmOCTwkp935Ok+vyLNTOM0t509nr5FxO9fanKvc1qO3L0nrqlYIGmBgsJICNxTiyu9fyUOPPEJ9QwPFYoFoKMxf/nwvw4YPx/eDvXQNF/q+T/OQZsaMHlW+PoAMPgo+SSIJMDDNefPm86tfXU9Pbw/7738AF174NRKJhA1sCMVBkdOCI69/hvd64tRGJB3JFOdMbeGakyeWqMNIv+AM0KZUYmD6H4RS2GBo2opn/k9Af3Ku5lsmFHvX7Mhm5zZC4eNw28uruenvi+gkhOtGUNkM+28X41enTWVMXRitFWCd0hB0FDxue3EFd7+4kqJTT8wVIDWpTIZd6yXXnzWNXYdEQPtoHBQaaXeCu2zGO9w7p4t80ePbB7Xwn0dNtPP1DyubbB3Ou+A87rrrLoYMbSGXz5OIxVgwbz5Nzc0Dg5YwWATyaUD/5iE22y49DY7QCGXnv8LH04Kjb3qJRb0xakOwMZPnq5Mb+O8T9gi6u62/qp3nn4GPq41uecoTzImFmVYEngRSOOw9tp5hjXFWr19PQuc5ZvIIfnDCnoytDeNZ93yJ8aZFaxKuw4HjmxnZUseby9aSVuDg4IbDtCWzLFjZzr67jqAh6iCU8WhR1qFNREK88vZiCvkcX5g8miljm832kcKYJ4EPxcKBbcK8l7CqnDKjz5r1AO+8M49YPI5SGtdxOf+886ittaunKztdxfQgwMqVq1ixYiWvvfYaXV2d5HI5EokaXNdIVpuOwCYfA6/39aVYsWIFixe/x5tvvkk6kyGdTlNbW4vjfIAieQAqG1I6nWFV60o6OzrpTSapr28o3ev/Toa0368BmvbhIwAlJEUkWSH485ut9OZcIlKRLebZfUw9h+8yBN9MVk3dYQaPolHN45fWopuSWNKdY/GGHjLFInWJ6CYqcw9Ym1G0dqZY1p5m6YY0Xdk8vb4gHHMJNFra1mllKfsYq6QZ9ko0V0ob+91IXibPnlEr9z/nQfsoISjY9/LsR1RM5FLAqt48G1J5ugsQijpE7D3jDmHJGEgDq3qLbOzL01NQuDG3HDbIU/ADc0FVGOALwIq+Iq1dfSxtT7OyK0dnLk9aCWJRl1BQlzayfnH2Q9A7Nn93c9iyhDIAlcFLjT1ToOj5NNXFKkJSemPP5trBWnAQ/OaV5Vz9xGpqowm08EBCpjfN9LEJrj9rH4ZGJVpptDTWGw08u6iNtmSeo/caS0MIjE+uNuZoIT7YQrO1GFC6X/3qufz+nntoHjqEQqFALBLh7X+8yciRI0thzEIE86y0ZXL/jJncccedLFjwLn3JPnL5PK7rEovFGL/9dhxzzLFcdPFFNNTXmUdLHT2oRNO4Vq5ayR2338ljjz/O6tbV5HIFCsUi0WiYaDTM+PHbc8IJJ3LxNy8mFon2I4znnn+B//mf/0aEQuArGhubuOf3v6Ors5trrruWp556ktVrVqOUJhQKs/1223PMF4/h0ksvJhKJmJMMpN2XRmjWrFnDf1z2bbK5AtJxUF6Bs75yBqd++VSwZuCbn32XZxauxo0lmN8h8fwYIeGT03mGRnx2qDP75MRUistPPICdmhr400sLeWDeWiIRh2wmyzGTR3P69D351aPzuf/t9fQUFDvUetx60ecZFzd1rICXV3Yz4/XFzFtdpCfjUdSgtcCRGjcsGdugOXbyWI7/zHjbXhSONq1JC8Gtz/6Dx9/rJB6K4heK7DQkxg+O34eo65YJQxtPp+fea+POp+cgIlEKwiHkZfnOcdPYc1gjAkV7OssP7nudPg+E9JFekSuP3Y9dhjUw681WZr69ghU9Gl9JQlIzug6O3nMsx03bnkbHtJ/2gubhN1t5cl4rK3tBexrpaIbVC47fcywn7rM9dS6gjYtgqWdoDVJSAJ5fsIH73lrKvPV5MjlQWqC0wJU+NWHNDkPDHD9lRz4/aSRxzONGvYChQ7uXEQi739G29astSigDIYQofQJEQg6xSAiru60QFExBCTTSNjis2Ly2N8sT724kHA7hYjwxnUiMxRt6yWeyTJ8wDBeBJ0BqswJ5+6F1TBzVQNQBrZXxHTGtfZteeouoIJQHHniQue+8QzwRx/d9Qq7LhV//WklCCd4JuzZpY0cH37z4Er7/nz9g5coVKKVACFzXRQiB7/usW7eeJ554nBdeeIkpU6YwfPjwUnqmXM3n/vvv54yvnMHDDz9CT08SBEjHIRQKAYqiV2T16tU8/thjvPjiS0w/4ACam5tLpDJn7jv87Kc/YcmyZSxZtIi169ax6867csEFX+Ovf72Xrp5etFb4vk8mV2BVaytPPP43XnvtdQ4//DBq6+pKo6AQgvYNG7jy+z9g3jtzWbJiJUsWvcseEydy8MEHl8rijldW87cFXbTnanCES1jYpi8EqZxiZafL8h6Hju4+jt17HCNqYjz0jzXc+04v7WmXVRvT6FicuesL/O7FxWRDCXwnjsDn+GnjaA6bJR3XPjafXz66mLc3FEkrl4wTI0MET0bwZIi8cljbm+eZ9zYyZ3kHe40fypCYWxoxlBDc+/IS/rYoS3sqwvJORdGDk/YZS8QxcnWg7kcInl+e5I7n17A2G2dVl6azM8lRU8Yytj4OCDrzPtf/fSULOiSrk5rVnUV22W4Ef3plGb9+bhmtKZc8CfLaJe95rE7C04va2NidYt/dR7C6O8flf36TO99sZ00mRF5J8k6IpC9Yk/J45t2NrFjbxd47t1ATdszJNXa6KKRkY6bITx+cx3XPLufdjgIFFafg1JDXDkUnhCfDZDzJ0h7FM/PW0bExzWd2GkbMFfb8rKAx2zVz1hXDyqal9rklfHTVuiFMQ5SbpGuiF1pZq4whEw28sWQjxtgIaIWjBa72SNTEmfXWep6cvxEEZi8W2ygDU7LW2N1TbGsvyTD/DJgRQiBIpVOcedaZ/O53d9Lc3ERTUxOZTJZUKoUQAq9YJJlMEo1GaRk2gldffZXTTj+d1tbWCoI2FXj3H+7h1FNPpW3DBlpaWohEwvT29NDXl8T3CiT7+sik09TV1TGkZSgvPP88X/nKV+jo6CjFFXJdQrE4DQ2NNLa0IITkvPPOZ/78+YQjMXLpFL3dPaQzacIhl4bGJppahvPUU08QjDOmvkzZOo5DfUMDifpGmpqawAkRHWAmd3WRkCoi/SLC7vZnCM5EprWH9oKRz8TrhlxqamKEamtoGNrCu+sUf3p9HaJhCBKNn02hvALCOjHe+MQCbn6+lUK4hpqaWpTSRAopxsTzjE7kcLw0vl+kNlZPTayF51f2cf0j88iaLQRLeY1G48TjCeKJCLXxCPFYBGXvm65qGzYg3BDRukYiiRpqaxLUxONIWY5LCkEiGiURj1ATryHUOJzrnlnJ/fM3kgtHUcrDz/Ti5TM44TCJeIR4bSOPzFnHL55YzpUPLuCFVSmiYYnrpdHZNCqTJyZd6iO11NcN5fGFPdz+wpKS9KQwknnag5/MnMM9r6/Hi9VRl2hAeoqo38PY2hzDoz5OIQMaahI1hGqa+OPbbfzP3xfiBS+gA38g88ZmecS2kQmDRSjBoCr615eFtJsWKIQw4vxjS7p4Yt4GEpEwWnsoHHwRQiNxpSITcrjh2cWszxUxdabN3Fw4+MJBa0NMyp7wYxjtw63l+aio5PCfX3UVf3/scYYMHYYQgr6+Po488gh+97u7+PvfH2fWrJlccsklaK3J5XIMGzaMRQsX8KMf/8TEZQtvwYIFXHH55YSjMerrGslmcyil+PqFF3LP3b/nwQce4I7bb+PoL3yBdCqF1pohLUN5/fXXueWWWzbJoVGOA2jyeRPXwQcdxHcvv4L//M/vc9ihh1LMFygWDcXX1Tcya9YsFi9aZGMIng5Gj2DqW16ME9TA/tsP5UtTx3Hc5OGEXUVOOwgBOU8zpjHOiXu18KXJTRw/aSSNUaMZkEIglMBRDghBwTOmZ5npY+fGKAeMq2PKyDqawi4vt/ZyxyvrkI1D0KEomUyevcfG+N2Zk5h50TTu+8Y+3HbG7kwa5pDJpnAUNNU08NSSLp5b1tmvg2htvLjNtECXulAZ5e7haA/Hz+LqojUalLUWBGUjBFopQtpYJ3syClcL9h2V4OKDh3PJYSOYvkMTxUyGotK4UhCqaWbWa+38Y02ecEiw14g4Xz9oNJd8bjSH7dxIrJhD+KbvhOsa+PuctSzuySIRuNpsnfr0og08sriHSHMLjgP5bIajd6vlT+dN4b6L9mPmN/bmxi9NYKeETzFXQLuKUGOCZ+atZPnGpJHuBf0kAvEhyeHDPLPVKOlbdPn0nbc2pvnvGW/Ro2JEHAchJRoX5Sl8BEqGcWJ1zN/Yx9/nrLWUaWaLRgQtu97r0jTqnwshBPPmz+c3N91EXUM9Ukq6Ojs5/PDDmTFjBmd+5Qz22XsqRx55BDdcfx3f+97lZDJZPN+ntq6Bhx9+hPnvLijFd+2117J+3Xpq6uooFosU8nl++ctfcsvNv+G0077MIYcezLnnnMPMGTP5/FFHkeztxZGSmpoa/viHP9Ld3Q2VBGAV6p7nUSwWueqqn/PYY4/y31f/gp/97Oc8+vAjnHPOuaT6+gAIh8N0dnUx5525pferRP8ytyO4Nf+eccAOXH/GPvz0xF1piisKypj2U1mfKSNruO6kCfzq1D34+Zf2Zmy9MTeXV58rtHbJK02NynPF4Ttw17lTufOCaVxz1gE0ufDiO8tZ15vBy6ZpT3ZS7yT54fG7se8OzQyLhBgeCXPQji1874u7U+MWKeDjSpdOP8Sc1jaT5WC5hnbwhYuWIZRw0LjIErHYAari3SUKLTSesCdgDliLoaRAS7OuTfiKUCHNOVNGcseZ+3D5YXtw2WG7c/NZe3LyZ0aSKxSNZCscdCiMzvZx6qRmbv/qNK48Ynf+46Dd+PWZe3Li1KHksx1oPCKuZENS887KJIDdghVeWbCcznSOQiZNX0cH4+IFrjhxIpNGNdASDjMiHuJzuw/n/KMn4vpptO/jSJdMARauS9ncO+UZRamv2UFjG/CxEYoOVqkqWynC5bW2Pr79+9mszEYIxWopigjZoiaTyZJwfFQhjVfUhLVDzK3hj7PXsi5v/PpNgzWVGiguRTDeCCro5p+DW269hb5kH9FolEKhQENjI7/4xS+IRjZdrXTpf1zCmO22I5vLE4nF6djYzjPPPAvAylWtPPzII9Q2NgKQTKfYd7/9uPDrF0BA0rZsHSk595xzKRaKbGjbQCqVYtHiRcyfP79fesFzfck+vvvd7/Lt73wLKStGX8fhggvOw3UdE78j0Uox5+05/eLYEqxGC4kihsL1BVKbzqmFxFVmo/Kglsq15eNQAAG+AuFnueyLEzh/+o4Mj7kkhKLO+jQdsvNIbjxhF67+3FiuPXIcvzh2Ars1miUglY3/M6PqGTMkgfZz+CKPCLv0JksCvsmn0KX8SXzrD4PNmSGWAL4Qhnzs+5lPAOseoT0QPnlXki8U2H9cDZd+YVeawpj4tKZGwCnTd6QpDLroI6WPLqaZvkMjl39xL4aEzCCgNYSB4/ceRXMEClpQ1FAIhVnd0WOz6aGBo3YbyQ3H7cTVnx/FL44ez/87egLDw06//APsNbaB0bUSoQQuLkUlWJ8slO6XS8/2MaNb2CYMAqEEBd8/85RGNkMojy/t4Nv3vMHSvhDxRA3aL5JNpmgUOS7Yt54/XLAnP/3ieBJ+L4VigVA0zrtdaf732cWl+My7SbNzmzUBDsILfGQUPY935r6DGw6ZjtvXx2c/+1n22H3CwKAAJGJRths3lnzBnFEkHYc33ngDgLlz59Ld3YvrRgCJl8tzxhmnQ0AmlGteo5m450Qu+/a3+Oall3DJJZdw0UUX0WjJqJJelfIJRyIccbjx4g3GHq1MZHV1dcSiMTyv3OlSGbtVxQeinIpZ8e2bjQu0XW2stSUUhV+RocrW4kttFIzaQ3hFxtbFOXS3llJAX0MRjdKw787DuOCgXThz/x0478Cd+cKkHcgoQVuyyLpknvV9BTb25VmVLBB2wwhdxLEat0Kh7IgoAY0KDlcAu9Ox0aEINO4ARb+wEnEQW+lBS6VmUaTGwReKVLHA/ru0UGNdt3xbLuDTHJGMiAnyQuGjEMUse4wZSqMrQJmy8y1JjahJ0FRfR9pXCMcnKxVtKSNV+ELjKzhoj3Gcc9CunL3fDpzz2d04eI+xZDzYkCyyPpmnLZmno69AR2+BsHQRStnacigo24PsuB+UhaHLbR+kB7k/lpuJCExRUvLwgg1ccffrrMmHiCdi9KVSqHQ3p0yu5a6v7cv3j57IhOY4X/7MOK44end0LonvecQjCe57bQ2vrjCM3P/VjOXHprbJ3U8SqXSKVDpFKGSsCImaBEuXLuXLp53BSSd/iZNO/hInn3IqJ538JU455VS+9OUzaG1dbVz7tSIUiTJ3jpEGOjo68X2FEIJisUi8toYJEwJiMg03gNYwbsxYrrvmWm68/gZuuOEGbrrpJvbYYw9zvyIsgCNlSU8yENFolIb6BorFoiEuQT8pZmtg1O4ScPGFQEmNbxWXxjG/HJ+ZWpgc+hjdmFQu2oeYgIhSJdVguW7Lz7RnC/x17jq+M/NtTrvlVU64/U1OuusNTrjjdY6//TXOvmM2SzsUoUjM2GuUY7YU7QcjUxnXA42jglXspm31Lz8TTmhhTauVZWPbnzajv6MESEm4YgU2OiAiiSslCdeQkhKGpHxtp+/C+PS4QeJS2KN7BY6Q+CpC0Z5II7WLkhpl+0FrX567Xl/Hxfe9y0k3v8JJt73KybfP5uQ73uSE29/g4nvnsCbvEHXAVb7RH8mANE2CukI8MPmxt7cS29ZiNougSgxMdZTtx08u6+TH98+lL1SP44ZRqU4OHe3w669M5qqT92LSkBhoy+AaTp86hm8evB0ylcQREXqcGq68/y1mr+oakC6bqdSys1JOQw7I2z2ZyhjYzT46tALla9ASrSXhSIxVq9fwl7/8lZkzZzHzgQeYMWMmM2fO5P4ZM7jvr3+hfcN6wo5Ae0VQPr5vOvqa1a0IYQ6T94sFGhsaGWK9cs103mq+rVJe2w2iSnkJpBhbM+aiRGuBKm2EVG4n1pcKoUErQ2QgTefYptZk4rWGTPO9ouNJq1gvha7Uy2isB6U5rsXDtzmXIMBB4KKQQgOCmXPbOP3WF/mvGXOY+XYnb3V4LMtolvUKlvQK3kuGWJp0yGgJIozWpo2qks7DmISlNlKJRtrtFwIfHgEqeHvzXmZC5JRcGDT9j3cRAUlKhZDWaGDrwpRo4Gph86JN+qU18tqqeIWLFLK0Rg1t16JogfC1CW9JQKAJAz6Su15ewRm/fYmfPTyfB+d3M7dHsyzj8l7KZUEfLEpKWvs8clKiCZkdFoVfIiNsvw1qzym1t23DIBAKdhd8y9BBcxKCgtLc/MR81vgh3HCYmmKa8w/ZkV+fsz+fm9BC2O7CpgGpnZJIfNFhO3P6tJFkkt244TAr0oLv3Ps6v311FQu60yRzHqm8Yl0qx+vtSWa8281vX17D9x9ayNd+9w/OuvU1zr7jVc668y3OvPN1zv/fN3lw3gZLLB+ilLaIoCFKsCONkA7xRA2xRJxYJEo8HiMeixOPxYjHovjFAtl0ilw2je8VS4rPXC5rLFs6aOqi3Oux2RdmOhk8Y4LbXdUqIISusEHZ937fTV3KCEJsRdAKmIPagtKVaFwFUgNotFA4ukztppRMYw6OVVFCgzDTkGDqEYi6wQT3r2+v5Yr75rIwGUbVDkWEa4mrPOPDXexdm+KIYR6HDyty8HCPBieP9n0ThfDsiVImdYFxSZC2syoZHDpnO5hV3JbLDaTwzFKQgKdtbP0RvJeuIE3j+tAvSL92aOyVm4OhFXvXlo/ZoMrkEQS3P72Eqx9ZRGshQaS2mbCjqSXJ+GiS/RrTHDqiyBHDCkxvgTpyFPHxpUaLCsto+TX7/d1WfHRC0cHHznGC70DGV6xN53GjNeRzBfYdV8M3D9mBuhCglPWhNW7HweNKK8JovnP0BI7drZF8X5J4LEGbF+W6xxdy7m0vc+Zdr3H2Xa9z7q2v8Y1bZ/Mff5jND+5/gz+9tIS3V3WwqivJG6s7eWRJF0+t9nh0eZYfz3yTRR2ZgbkfFATSu6lfTSqZ5OQTT+ChB2fy4KwZPPjATB6YNZMHHpjJAw/M4oEHZvHggw/y4EMP8eCDD/Hoo49y8803A9DU1ISyeg0hJIVigXw+NyBFKvw7TFkHBNPfIvNhm8WHQbnzgBlkHGWUl2ZkdwYQShmGdLYEybLePLc8NZ98uIbGcBg3nWLXesHPT5zMPRd/nrsvPYLbLjyQOy48kN9+bTrbN4XIFctlN3BXYonCEeaEBWWo22bfWnLM0ACAoxWO3qyz1T8RgtmtPdz07BKoqScRlniZNFOHCa45bW/uueRI/veiQ7nzgs9y54UH8l+nTaM54uBpDy00GnfQW8hHJxSLgFfMd/OrJuQwvmUIquDha0nEimjgm70zcO2pgYD2EcFxGUpTE5L8+KRJHDguSm+yB+FECScaade1vNHt8mJ7iDe7XDqzmt2Ghfn6wdtxy/nT+fO3DuVPlxzKvRcfxo+PGMNOkSx1IUGGOOu6Px5CCYfDuKEQShktQiGXIRYJcdihh3DE4YdzxBEDP0dw+OGHlz5HHnkkBx54IEDJa1ZrTSgUoqOjg3VrzT4klQiIw/d9enp66OzspKuri87OTgqFsub+k4Spx3ITDY50UzigTV2XIba5+b21MsnaXkEkEqKgBTUU+c5RO3LKnkPYKeHQ7EjqhCQhJI1W4lCOmb5pLTYhWE9oc9SuMFMYH2sOrtCtYElQCklRO/iV0uKnALOXbqCHONKNkPfzDIkLrjxhCsfsOITxUZcmR1IvICYE9cIh7Eu0EkZ/UmHXGix89NKxOipDEGaExopSLnDUbiOIFJKEHEFbr097RptkBWaMEMLuiSFK2zoqKUEphsRDXPuVvTlr71FEs0ly3UlIZ4hmkozWHRy/U5SrTt6NOy44gF8ctxef37mJXepCjE+47NMS47uH7cIPT5pMnBSe5/ffbmAQUVuToKWlhXzOjIaJRJynn36Knh6jTDYzkUDVVRYzs9lsKY5gujJu3DjC4TBKaxzHQfk+Tz/zTClcEDaQTubMmcuECROYPHkvJk/ei4kT9+Sll14y4Qa9uWwOA9KwfVYBBcdFCcesThf0V4qaxmIf2bp8bujN4MswWkBKC6KJGBOGG18WjY/WZpsNgO68piNVKDkbCARS9Z9WaFeSK+lYNSnP7BwI4FAwEw1bL+mCR9EJXPc/HdBAbzJLVBp9Tt4rMnpYnF1bYrb2lWlttl+liprevMYRxiHu48BHJxQoZd5k0SqX7P/7jW9kXJ3xiF3bm6U9XaxoSJVzRGsOthWmpQJdYHhM8vPjd+eW8/fjii/swqWHj+eHJ+zB7d/Yj9+ePZXTPjOaMQm7FtOazXXwBThql2am7jCEfKGwzVaLbcHxxx9XIoV4PMGiRYu44YYbgQplKiJQdzF79myOPPJIbrwxCGPKZK+99mKHHXcgnUmj0MQSCe6//37aN3aW0qqc2rz66mu0tbXR15eiu7uHjo4u6uuN2bgS/adCHwd0yTgK2jqA2XOwBYDXXxErbLjS/S1DSFC6iIsmLCXZoqIra8zcQrtWi2PqYNYbS1m7MUPUddFSG/1chas8wNDGWjxP4esiwoV1vXkWbSiTPAiQLku78zw6exluKPwxdcNtQ0BpAnARaOkjhEYSoitdoM8L7tqNUq1UNeP191ibUzhOCLQ2U7hBxqD0MLMi0xKJNp6twVuPa4qy27hmfOXRWRQsa7OjtpVShLZkYq8JzBk/xswmUdp0wf3H1PK16WO59KDtOWfqSKa01BMWZii0CnoLZQrT7EOAA0wbPwInl6fgDX4BBjj11FOZNGkS3d3dKCS19U1cf+OvueOOO60kYio4m81y//33c+KJJ/Hyyy9z2WWXcfbZZ7N8+XIAamtrueiiiylkM/haE0vEWb9+PRdeeCHLV6zsl+azz73AtdddR01tPZFolHyhwJSpU9h1wq79wn28CLpYpa3PdO1ax0doM92NuWGWrOtmadajAKzPeGSKhgz6T4XeH02JKJICQnskpE867/GHl1vZWLTH5ApJt5bc++Ya7nphBSJagyMkSit8KSgOINWdhjXSIE3HCjkOGSJc+7dFPL8yybp8hFUpwWMLO/jOH99gfqdHOOxsq6b6Y0HlW9TFw2Q0gE88HGLthgJ3P7+MPsCYSgTr85rrX1jGH2evRsZqAENAZvFAEJsYFIl262pyK1B+SYESrhkRtNGZ7Dq2Fu1lSGqHd1vNSCsxJGC6vTYjmB3ZsNYJoV0z5mjK0wX7jK81vtbmGA/rPKRtoy4Tm8nRpFFxEiFFbzpw2vroBVcJpaG+rparf/lLQqEQ6WyWaDyOpzTfuPgSpn/2II46+gscc+xxHHjgZznzzLNIJnsYPnw40WiUu+++m4ULFwJGPD3/vPM49vgT6G7fgAbqGup5+OGHOeTQQ/j8UZ/n+BNP4JBDDuGUU05hQ3s7iUSCbC5HsZDju9/9Lon4wG0kPj4E8mhQCQ7GIzSMYPcRjXiZFEJDIhRiYafP1257kS/f8jTfuPkxVnanDA9U2l8/AFO2b2RUbZhU0Uwf/XiCv76zkXNufYEfzfgHP5o1h7NvfpH/enQZ7fkYUii0MgfLuVrhKdtlrBZ98thGdqqXFLIKqSSRSIg323J88w9zOf2W2Zxx66t8Z8Z83upU6HDYeGkPbtP5yJi88zBqlUfR04SExolEue2lVs6++UX+30Pz+O79r3P2b5/lumfXkHVqCXlFhFTG4uX7pf2ATU1uXT18EAaHUETpPxBld6Sg9PffvoHmiAZHMHdFG0kV6DLMfqKOFuZTQS/BzulYb0u0WVCuhcZHoYTxrjQsa6ZbWlg6sQ5Fxgyt2aWpjrEttaQCncU2NQrTZaQ93nngzCGw8Gjg8587gt/+5jdov0hnx0YioRB19XUsWLiYJ598iscfe5wFCxdSU1NDPB6nq6sLrTVXXXUVRx99dGnKFAqFuOnXN3HwoYfRtaGNfC5Pc3MT3d3dPPvcczzyyCO8Nns2WilqEgn6+vrIpPq47Fvf5sQTjuuft8DnYsDItgmEMW0KUZ4ZDDRD26vlstBBbQVlWm5OAvjc5NEMCfnk81kjlkditCZd3mhzWJlUFOyjEo2PxEPgCYlnF1iUYzIBd24Ic/oB45HpPjL5Ap7j4sQSvNsV5c55aW6d38Nb7ZJ8vsjEEXGm7DCMfCGJ7xSJIEn2Fukxx1CiNYyucThj+njCuT4KeQ+0IBINk3Vd1iQFazIh+nyHOB4HTKjH0XmK2sXHQWnrLVsBhcTXLkXh4JUGQkw4XaoQoyw2cgIKB/UBWiRttW5BuWgdKH3M3X23a+L86ePw+rrp83w8x4VIgn+0S+6a08GfFvSyqDcCuTyHjath12EJej2FJ0BJhzWd6dKqf5OHfuL+NmNwCMV0udKvEBCi7D8xeXgjE8c0IX3Fis4ii7uCV7DUo7H6E+PoE4hqJlppWrj1RRAIXCQh+3GC7lI6z93s5+Db1chon8aEwyn778TwYKW9PbhqsxjQ69LpFFp5bGxro7e7i/a2NrPHSQkaGeiYga9+9SweenAWn91/X3q6NtLZ3oaXz1hPAkUhn6Ozs4P29o1MmjSJhx9+mCuvvHITs++Y0SOZNeN+Lr30Uhw0G9rWk+7rQ/sKoaFYKNDb283G9jaGNDdyyy03c92111TkC7xikUIuQ3dHG90dG0in+vD9irxbZZ35qunu6iCT7KGjbR2gyGT7W8V8X9GxcQOpnk46NqxFK49cEEaYcvWwUwvtcfD29Vx29O7U6W56ejrIppJ4vodf9FCFXKnh6mIGke6CbBc61YnK9VXUj4bSCYSKCw7YgWtOm8j28RzF7k6y3d2oQhrl51CFFGE3x/F7NvLr03fnxN0biCS7EcleooUkS1tXsWy9WVinrHPaafuM4+enTmZMrEC2q5tUT5JcJkk224POJdkukeOXJ0zg0sO2Q/asR6a7cTLd6L4+pF9uQ1JrdLoHke5G9/XipLpxK0zWBrbstcLP9SLSHYhUNyLTg8ibZQ4KzOrw4P21RuT70JkOdKYbp68TmTeu91qbhQCXfG5XrvzCrox2smR6NpLuS6K9LBSyiLxHo1Pg7GkjuObUCUzbPky+cwOhVB/a17y1eDXresyU3HoD2T2kg9z0V2RvCdu8Y9uHxU0vr+a6xxYg3DA/On53zpzcAlpZvUn/VZ0fHraDWHcBH3CUkYJySHxfWZdnUxlbo6h88sknmT9/PqFQCM/zCIVCnH322dTU1HxgHMVikYceeojZs2ezdu1afN9Da3AdhyFDh7LPPvtw4oknEovFNhtP5bW3336bv/3tbyxZsqRkGZJSUltby8SJEznhhBMYPXr0Js+1trYya9asUpxSylLYoNqDsLlcjr/85S90dXURCoUoFotMmzaN/fffvxRnMpnkvvvuI5lM4jimPA88cDpTp061DbI8vjk62NbQ5bXVXTw6Zw3rkpqCr4mHJJNGuJy27440RMPMbd3Ako29ONIFpYhGQnx2l5HUhAKrkLZqf8yhcsCaVIGXFq9m3vo8fUWJ6/qMqNFMGzeC/cc32+0DCsxetBZD5xpHe0zZcRSj6yIIPDTh0vsv78nx3MJWFnd65DxNLKLZfUiYQ3bdjtG1YdIFjxffXUVGmQ3MhdJM22U0wxPGESJX8Hhm0RoKvgLhUPA89h7TzPjhDXZJQnnQSXua1xa10pP3EFKifI+dhzWwx5ihoEFQNC1ZhCgUFS++t4aOnEfEkWSLHuOaE+y3/TAkCiXc0lC+ojvLM4tWs6TTp1BQiLBmTL3kkPGjmDTKHPOyoivFW8vbcYSDJxxcneeAnYbTXJcwBlqME6LxTzZlv8ko+wH4xAjljbYMF/3vq6xIO1wwZShXHb872KZimuJHFJY0tjkL86MkoQiEVgjpG+Fay00674dBZbENjG9zBPFB2Fz4gR1+a7C1zwTpBX+VUh9oAdPWTP3+YSrKHewkButbpECEAHMQnNYQCqRJo27p5whcgrZT3uAnZpGgCKZv9h0DI3z/CYiPVhIxwKoTQPv26A5hDQjQzwIUvEXpygf0Ka1NuypJ1P3vorSPECZ3ojTeWw/oAfB1YJZQ+EKBNmSxuepU2kdiDsdTGhyhSm78AbHLTd7h/V/EV3YppDCfTcpgK7G5qvxYsMvQCCMaohSVZEFrB+15q0fRDF42NKaJCQBhZ+IaT5q5rdbBQqitR9CZgu+Vf9+v41aGez++VsouO3if+0HcQZj3CzfwfmWeBt4b+D34K6X8wLDYeDcbJghQ8oINuo3GFw5F3JL0HkYTsQe9oa25V2jjNR1I+Rp7bnZgLTTvIxS4OvCqVWhttop2ABe7dYBSKKXwkeYB7ZkISxHbP3ZVcDA91lanEvREoZXZZdA+qtHGx0WbVUZa2zzbfX5E0AG10ekpjZnWWKI1Oj6bF2x8yjcMqQIXB6O/MndlSRITtpxNBhVm3bVv9kLRIJWHI3w0Al+b6YqwejMbrXkPAQofXxeMjjGITiu0Bil8lCia4g4klZK8ufUYpJ68ZdQ5DuOaosScEEs78sxdZzbzMYq9QYDA6FuEWXrtY5RXwfIvs6rz/Ung/SAq18xU/B14rRLBSF4ZbiCkNJLSB4WpvP9hwgy8PjDs+92r/D3w3ibXwboAmHIv2rl4MCMXwjguYs92MhKFY8QSYfYZUVLa4dQeKyv7SycgjLOk0Faf5iCEW5KENAKEi5YSKSSOtnkUrr1neo/GdKzKtXcISspobX8HLBGsLTPOl+adHKxkU7pXeaqQfXdhvjs4yNJWByZBCThI4xsiTbwI03kFyqyvEaYjB0KTsKQHEoWLxjHSl3RMWWgHqUUpdiOVG7IP1keZSaODFGGbH1PGWhhDh3l/s99L0CE/jNXnEyIUk8PtWpqJ4NOpI7y+3O6eRYV89RFgiRhs5QaNB+v846LtatUqBhuVza5SzJYl6UGAkgi78x4Yd3i0rrDnBIdrBN1TlQgGsHvg2C5reorpOLbWzVN+cLnCEuLbT5nkDAzJGaILnlflw9xtXoWw9icdTCKCKbrp5OUxPHiP4P2tKUcbqtBC2rQCYguILsifjdPGUZIOAlKxV4PyHdiSdZmbDISwMpgGrcz2DNrKHcI3op4GoTXSHmXS33AsTL1tI6l8QoRiEIvGzCbFoRCLVvVQ0MaHpFwKHx4iiEYbkdUY44LpT0UlV/GxQVojaHn6E8A2zMriF9jOaRBs6FOpvrQ2wIruY3UzRntYgsBHaCP2l5/WdvGpBhzMhhD0IxjKcpTp5Aj7XGX8VtshhNXUGIkjcFGofFpb3ZC2fGfyaVK1sVpCMZKawkgPJjHHWjgDycvsnVw56QjiKEVbkjKMNKLpN0u0DwUimSl/k2M79ZcBkRkaCLJcWbalxLcSnwyh2Dfs6uvDl4K4Cxu7Mqzvs1sCVm5E8xFgClPa0wStmKmxVVdZSlUMJkybM2OnmWIEDdS2TmH2CTHN2XRshR2ltUQqyhsXBfuClNwHgtAmJSPFGM9YJYxcE3jaBHRg4saK/4E7gnm60ivXqEClHaVNjm0PNb908IxbIfEYCOsd7tgcgDkkzuxSF3RMs1OdjdVOTRyEtqc52Pxoe8QvVkcUkIOhWbu1gTaKkDLpqfJCRg3SSiH9uSAot0CuMXUSpOEjzR41Wpo8YV/MTrlKGd8GDAqhlEjM6Nbw0OjgjDVlMucD89d04UuHsCNZlyqwqH2gnf6jIXj30jhVMVHexnKpYhtQLltL5KUGvPlSrwxfqqrNBDc0YcNt8jEo1W7QuQbcsQqNiqdEScooha0IA3Y0txdKz1XoTSoCW1Q8Y2F+mvIISiX4r/8/a54NErLJSITdQyUgZaObkaXIP/hdg5QG5suQZb9cldMuYcAz24BBIRSCMcQORgLsknHbsITg2fd6eHdtlng4glCSPuWypD1witp268v7YZOi2FxLreITQGWZi35NLfhVCtEv6MC66v+sIQPzu0w4AUwX6Rd3v7ubv/7hISoM1gH7VBJPMEUa8MgWMlJ+4/IUaxNUllOQ7ibYzLVS2kZHtCkBbEUGPwDi8ssv38ZZ0v9dXH311VxxxRX9fgeoXq9er16H/x9I25qmBbNBBQAAAABJRU5ErkJggg=="


C = dict(
    navy="#0B2545", navy2="#13315C", teal="#2A88C9", rojo="#D64545", ambar="#F2A541",
    gris="#8D99AE", azul="#0E7490", verde="#2A9D8F", fondo="#F4F6FA",
)


CSS = f"""
<style>
.block-container {{padding-top: 1.1rem; padding-bottom: 2rem;}}
.banner {{background: linear-gradient(90deg, {C['navy']} 0%, {C['navy2']} 55%, {C['teal']} 100%);
  color:#fff; padding:18px 26px; border-radius:14px; margin-bottom:12px;
  box-shadow:0 4px 18px rgba(11,37,69,.18);}}
.banner h1 {{color:#fff; font-size:1.55rem; margin:0; font-weight:800; letter-spacing:.01em;}}
.banner p {{margin:3px 0 0 0; opacity:.88; font-size:.92rem;}}
.kpi {{background:#FFFFFF; border-radius:14px; padding:14px 16px 12px 16px;
  box-shadow:0 2px 12px rgba(11,37,69,.08); border-left:6px solid var(--c); min-height:112px;}}
.kpi .t {{font-size:.72rem; color:#5A6B85; text-transform:uppercase; letter-spacing:.07em; font-weight:700;}}
.kpi .v {{font-size:1.65rem; font-weight:800; color:{C['navy']}; line-height:1.25; margin-top:4px;}}
.kpi .s {{font-size:.78rem; color:#7A8AA0; margin-top:2px;}}
.kpi .bar {{height:6px; background:#E6EAF1; border-radius:4px; margin-top:8px; overflow:hidden;}}
.kpi .bar > div {{height:6px; background:var(--c); border-radius:4px;}}
.alerta {{padding:9px 14px; border-radius:10px; margin:5px 0; font-size:.88rem;}}
.alerta.roja  {{background:#FDECEC; border-left:5px solid {C['rojo']};  color:#7A1F1F;}}
.alerta.ambar {{background:#FFF5E6; border-left:5px solid {C['ambar']}; color:#7A4B00;}}
.alerta.verde {{background:#E8F6F3; border-left:5px solid {C['verde']}; color:#145A50;}}
.alerta.azul  {{background:#EAF3FA; border-left:5px solid {C['azul']};  color:#14425A;}}
.seccion {{font-size:1.05rem; font-weight:800; color:{C['navy']}; border-bottom:2px solid {C['teal']};
  padding-bottom:4px; margin:16px 0 10px 0;}}
.logo-box {{background:#fff; border-radius:12px; padding:12px 10px; text-align:center; box-shadow:0 2px 10px rgba(11,37,69,.10); margin-bottom:8px;}}
.logo-box img {{max-width:100%; height:auto;}}
.logo-ph {{border:2px dashed {C['teal']}; border-radius:12px; padding:16px 10px; text-align:center;
  color:{C['navy']}; font-weight:900; font-size:1.25rem; letter-spacing:.04em; background:#fff;}}
.logo-ph small {{display:block; font-weight:500; font-size:.7rem; color:#7A8AA0; letter-spacing:0;}}
.chip {{display:inline-block; padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:700; margin:2px 4px 2px 0;}}
.chip.ok {{background:#E8F6F3; color:#145A50;}}
.chip.no {{background:#FDECEC; color:#7A1F1F;}}
.chip.info {{background:#EAF3FA; color:#14425A;}}
div[data-testid="stTabs"] button p {{font-weight:700;}}
</style>
"""


def norm(s) -> str:
    """Normaliza texto para comparar nombres de columnas (sin tildes, espacios ni signos)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def find_col(df: pd.DataFrame, *cands, parcial: bool = True):
    """Busca una columna por varios nombres posibles (exacto primero, luego parcial)."""
    mapa = {norm(c): c for c in df.columns}
    for c in cands:
        if norm(c) in mapa:
            return mapa[norm(c)]
    if parcial:
        for c in cands:
            k = norm(c)
            if len(k) < 4:
                continue
            for nk, orig in mapa.items():
                if nk.startswith(k):
                    return orig
    return None


def to_num(s) -> pd.Series:
    """Convierte textos tipo '$1,367,400.00', '.00', '68.32 %' a número."""
    s = pd.Series(s)
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").astype("float64")
    t = s.astype("string").str.strip()
    t = t.str.replace(r"[\$\s%]", "", regex=True).str.replace(",", "", regex=False)
    t = t.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaN": pd.NA, "-": pd.NA})
    return pd.to_numeric(t, errors="coerce").astype("float64")


def limpiar_codigo(s) -> pd.Series:
    """Referencia limpia: mayúsculas, sin espacios, sin '.0' de Excel."""
    t = pd.Series(s).astype("string").fillna("").str.upper().str.strip()
    t = t.str.replace(r"\s+", "", regex=True)
    t = t.str.replace(r"^(\d+)\.0+$", r"\1", regex=True)
    t = t.replace({"NAN": "", "NONE": "", "<NA>": "", "NAT": ""})
    return t.astype(str)


def limpiar_lote(s) -> pd.Series:
    """Lote limpio (conserva el '*' para poder detectarlo)."""
    t = limpiar_codigo(s)
    t = t.str.replace(r"^[^A-Z0-9\*]+", "", regex=True).str.replace(r"[^A-Z0-9\*]+$", "", regex=True)
    return t


def clave(s: pd.Series, es_lote: bool = False) -> pd.Series:
    """Llave de cruce: sin asteriscos, sin ceros a la izquierda."""
    t = pd.Series(s).astype(str).str.replace("*", "", regex=False).str.strip()
    t2 = t.str.lstrip("0")
    t = t2.where(t2 != "", t)
    if es_lote:
        t = t.where(~t.isin(["", "NOBATCH", "SINLOTE", "NA", "N/A", "0"]), "SIN LOTE")
    return t


def tiene_asterisco(s) -> pd.Series:
    return pd.Series(s).astype("string").fillna("").str.contains(r"\*", regex=True)


def tipo_asterisco(s) -> pd.Series:
    t = pd.Series(s).astype("string").fillna("")
    return np.where(t.str.contains(r"\*\*", regex=True), "**", np.where(t.str.contains(r"\*", regex=True), "*", ""))


def _una_fecha(v):
    try:
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        if isinstance(v, (pd.Timestamp, datetime, date)):
            ts = pd.Timestamp(v)
        else:
            t = str(v).strip()
            if not t or t in ("nan", "NaT", "None", "<NA>"):
                return None
            m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
            if m:
                ts = pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            elif re.match(r"^\d{5}(\.0+)?$", t):
                ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(t)))
            else:
                ts = pd.to_datetime(t, dayfirst=True, errors="coerce")
        if pd.isna(ts) or ts.year < 1950 or ts.year > 2200:
            return None
        return pd.Timestamp(ts.year, ts.month, ts.day)
    except Exception:
        return None


def parse_fecha(s) -> pd.Series:
    """Convierte fechas mixtas (datetime de Excel, 'YYYY/MM/DD', 'DD/MM/YYYY', seriales de Excel)."""
    s = pd.Series(s, dtype="object")
    cache = {}
    vals = []
    for v in s:
        k = v if isinstance(v, (str, int, float)) else repr(v)
        if k not in cache:
            cache[k] = _una_fecha(v)
        vals.append(cache[k])
    return pd.Series(pd.to_datetime(pd.Series(vals, dtype="object"), errors="coerce"), dtype="datetime64[ns]").set_axis(s.index)


def estado_venc(fechas: pd.Series, dias_alerta: int):
    hoy = pd.Timestamp(date.today())
    dias = (fechas - hoy).dt.days
    est = np.select(
        [fechas.isna(), dias < 0, dias <= dias_alerta],
        ["SIN FECHA", "VENCIDO", "PRÓXIMO A VENCER"],
        "VIGENTE",
    )
    return dias, est


def leer_csv_flexible(data: bytes, sep=None, header="infer") -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            txt = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if sep is None:
        primera = txt.splitlines()[0] if txt else ""
        sep = ";" if primera.count(";") >= primera.count(",") else ","
    return pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, header=0 if header == "infer" else header,
                       index_col=False, keep_default_na=True, on_bad_lines="skip")


def detectar_encabezado(raw: pd.DataFrame, obligatorios, alguno) -> int | None:
    for i in range(min(40, len(raw))):
        vals = {norm(v) for v in raw.iloc[i].tolist() if v is not None and str(v) != "nan"}
        if any(o in vals for o in obligatorios) and any(a in vals for a in alguno):
            return i
    return None


def unicos(cols):
    vistos, out = {}, []
    for c in cols:
        c = "COL" if c is None or str(c) == "nan" else str(c).strip()
        if c in vistos:
            vistos[c] += 1
            c = f"{c}_{vistos[c]}"
        else:
            vistos[c] = 0
        out.append(c)
    return out


def parse_gs1(codigo: str) -> dict:
    """Interpreta un código GS1-128 / DataMatrix: (01) GTIN, (17) vencimiento, (10) lote, (21) serial."""
    s = str(codigo).strip().replace("\x1d", "|").replace("]C1", "").replace("]d2", "")
    res = {}
    if "(" in s:
        for ai, val in re.findall(r"\((\d{2,4})\)([^(]*)", s):
            res[ai] = val.strip("|").strip()
        return res
    if not (s[:2] == "01" and len(s) >= 16 and s[2:16].isdigit()):
        return res
    i = 0
    while i < len(s):
        ai = s[i:i + 2]
        if ai == "01" and len(s) >= i + 16:
            res["01"] = s[i + 2:i + 16]; i += 16
        elif ai in ("11", "15", "17") and len(s) >= i + 8:
            res[ai] = s[i + 2:i + 8]; i += 8
        elif ai in ("10", "21"):
            j = s.find("|", i + 2)
            j = len(s) if j < 0 else j
            res[ai] = s[i + 2:j]; i = j + 1
        else:
            break
    return res


def gs1_fecha(yymmdd: str):
    try:
        yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        if dd == 0:
            dd = 28
        return pd.Timestamp(year=2000 + yy, month=mm, day=dd)
    except Exception:
        return pd.NaT


def fmt_num(x, dec=0) -> str:
    try:
        if round(float(x), dec) == 0:
            x = 0.0
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def fmt_cop(x) -> str:
    try:
        signo = "-" if x < 0 else ""
        return f"{signo}$ {fmt_num(abs(x))}"
    except Exception:
        return "$ 0"


def pct(a, b) -> float:
    return float(a) / float(b) * 100 if b else 0.0


@st.cache_data(show_spinner=False)
def hojas_excel(data: bytes) -> list:
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


@st.cache_data(show_spinner="Leyendo Templete / Kardex…")
def leer_templete(data: bytes, nombre: str, hoja=None) -> pd.DataFrame:
    if nombre.lower().endswith((".csv", ".txt")):
        raw = leer_csv_flexible(data, header=None)
    else:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=hoja if hoja is not None else 0, header=None, dtype=object)
    h = detectar_encabezado(raw, {"ITEMNUMBER", "REFERENCIA", "CODIGO", "REF"},
                            {"BATCHNUMBER", "LOTE", "BATCH", "CANTIDAD", "PHYSICALINVENTORY", "PRODUCTNAME",
                             "DESCRIPCION", "NOMBRE"})
    if h is None:
        raise ValueError("No se encontró la fila de encabezados (Item number / Referencia) en el templete.")
    df = raw.iloc[h + 1:].copy()
    df.columns = unicos(raw.iloc[h].tolist())
    c_ref = find_col(df, "Item number", "Referencia", "Codigo", "Ref", parcial=False) or find_col(df, "Item number", "Referencia", "Codigo")
    c_lot = find_col(df, "Batch number", "Lote", "Batch")
    c_col = find_col(df, "Color", parcial=False)
    c_cla = find_col(df, "Clase", "Tipo", "Categoria", "Tipo producto", parcial=False)
    c_ser = find_col(df, "Serial number", "Serial", parcial=False)
    c_qty = (find_col(df, "Physical inventory", parcial=False)
             or find_col(df, "Physical inventory", "Cantidad", "Existencia", "Total available"))
    c_des = find_col(df, "Product name", "Descripcion", "Nombre")
    c_exp = find_col(df, "Expiration date", "Vencimiento", "Fecha vencimiento")
    c_loc = find_col(df, "Location", "Ubicacion")
    c_wh = find_col(df, "Warehouse", "Bodega")
    out = pd.DataFrame({
        "REFERENCIA": limpiar_codigo(df[c_ref]),
        "DESCRIPCION": df[c_des].astype("string").fillna("").str.strip().astype(str) if c_des else "",
        "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
        "CANTIDAD": to_num(df[c_qty]).fillna(0) if c_qty else 1,
        "VENCE": parse_fecha(df[c_exp]) if c_exp else pd.NaT,
        "UBICACION": df[c_loc].astype("string").fillna("").astype(str) if c_loc else "",
        "BODEGA_SMITH": df[c_wh].astype("string").fillna("").astype(str) if c_wh else "",
        "SERIAL_TPL": limpiar_codigo(df[c_ser]) if c_ser else "",
    })
    # Clasificación: CAP (capital) o ubicación INS... = INSTRUMENTAL; Non-Cap = IMPLANTE
    color = df[c_col].astype("string").fillna("").str.upper().str.strip().astype(str) if c_col else pd.Series("", index=df.index)
    clase = df[c_cla].astype("string").fillna("").str.upper().astype(str) if c_cla else pd.Series("", index=df.index)
    ubic = out["UBICACION"].astype(str).str.upper()
    es_ins = (color == "CAP") | ubic.str.startswith("INS") | clase.str.contains("INSTRU|CAPITAL|EQUIPO", regex=True)
    out["CLASE"] = np.where(es_ins, "INSTRUMENTAL", "IMPLANTE")
    out["SERIAL_TPL"] = out["SERIAL_TPL"].replace("SERIALNUMBER", "")
    out = out[(out["REFERENCIA"] != "") & (out["REFERENCIA"].map(norm) != "ITEMNUMBER")].copy()
    out["K_REF"] = clave(out["REFERENCIA"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True)
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Procesando archivo NAL (inventario nacional)…")
def leer_nal(data: bytes) -> pd.DataFrame:
    df = leer_csv_flexible(data, sep=";")
    df.columns = [str(c).strip() for c in df.columns]
    c_tip = find_col(df, "TIP", parcial=False)
    if c_tip is None:
        raise ValueError("El archivo NAL no tiene la columna 'TIP'.")
    df = df[df[c_tip].astype("string").str.strip().str.upper().isin(["REF", "COM", "LOT", "SET"])].copy()
    c_bp = find_col(df, "BODEGA PROPIE.", "BODEGA PROPIETARIA")
    c_be = find_col(df, "BOD-EXISTENCIA", "BODEGA EXISTENCIA")
    c_cod = find_col(df, "CODIGO", parcial=False)
    c_ser = find_col(df, "SERIAL", parcial=False)
    c_nom = find_col(df, "NOMBRE", parcial=False)
    c_lot = find_col(df, "COD. CLIENTE", parcial=False)
    c_fec = find_col(df, "FEC. CRE", parcial=False)
    c_qty = find_col(df, "CANT. ACTUAL SER", parcial=False)
    c_cmp = find_col(df, "CANT. COMPO-SER", parcial=False)
    c_cos = find_col(df, "COS. SER. ACTUAL", parcial=False)
    c_set = find_col(df, "NOMBRE  SET", "NOMBRE SET", parcial=False)
    c_lin = find_col(df, "LINEA", parcial=False)
    tip = df[c_tip].astype("string").str.strip().str.upper()
    es_rl = tip.isin(["REF", "LOT"])
    out = pd.DataFrame({
        "TIP": tip.astype(str),
        "BOD_PROP": pd.to_numeric(df[c_bp].astype("string").str.extract(r"^\s*(\d+)")[0], errors="coerce").astype("float64"),
        "BOD_PROP_NOM": df[c_bp].astype("string").fillna("").str.strip().astype(str),
        "BOD_EXIST": pd.to_numeric(df[c_be].astype("string").str.extract(r"^\s*(\d+)")[0], errors="coerce").astype("float64") if c_be else np.nan,
        "BOD_EXIST_NOM": df[c_be].astype("string").fillna("").str.strip().astype(str) if c_be else "",
        "CODIGO": limpiar_codigo(df[c_cod]),
        "SERIAL": limpiar_codigo(df[c_ser]) if c_ser else "",
        "NOMBRE": df[c_nom].astype("string").fillna("").str.strip().astype(str) if c_nom else "",
        "LOTE": np.where(es_rl, limpiar_lote(df[c_lot]) if c_lot else "", ""),
        "VENCE": parse_fecha(df[c_fec].where(es_rl)) if c_fec else pd.NaT,
        "CANT": to_num(df[c_qty]).fillna(0) if c_qty else 0,
        "CANT_COMPO": to_num(df[c_cmp]).fillna(0) if c_cmp else 0,
        "COSTO_SER": to_num(df[c_cos]).fillna(0) if c_cos else 0,
        "NOMBRE_SET": df[c_set].astype("string").fillna("").str.strip().astype(str) if c_set else "",
        "LINEA": df[c_lin].astype("string").fillna("").str.strip().astype(str) if c_lin else "",
    })
    # Nombre del set para todas las filas a partir de la fila 'SET'
    sets = out[out["TIP"] == "SET"].drop_duplicates("SERIAL").set_index("SERIAL")["NOMBRE"]
    out["SET_NOMBRE"] = out["SERIAL"].map(sets).fillna(out["NOMBRE_SET"]).fillna("")
    out["K_REF"] = clave(out["CODIGO"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True)
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Leyendo Valref (validación de referencias y lotes)…")
def leer_valref(data: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(data), dtype=str)
    else:
        df = leer_csv_flexible(data)
    df.columns = [str(c).strip() for c in df.columns]
    c_ref = find_col(df, "COD. RELACION", "Item number", "Referencia proveedor", parcial=False)
    c_int = find_col(df, "R E F E R E N C I A", "REFERENCIA", parcial=False)
    if c_ref is None:
        c_ref = c_int
    if c_ref is None:
        raise ValueError("Valref: no se encontró la columna de referencia (COD. RELACION / REFERENCIA).")
    df = df[df[c_ref].astype("string").fillna("").map(norm) != norm(c_ref)].copy()   # quita encabezados repetidos
    c_nom = find_col(df, "N O M B R E", "NOMBRE", "DESCRIPCION")
    c_ean = find_col(df, "REFER-PROVEED.", "EAN", "GTIN")
    c_cos = find_col(df, "COSTO PROMEDIO", "COSTO")
    c_pre = find_col(df, "PRECIO VENTA", "PRECIO")
    c_lot = None
    for cand in ("LOTE", "LOT", "BATCH NUMBER", "NUMERO DE LOTE", "NRO LOTE", "NO LOTE", "LOTES"):
        c_lot = find_col(df, cand, parcial=False)
        if c_lot:
            break
    eval_cols = [c_lot] if c_lot else [c for c in (c_ref, c_int) if c]
    texto_eval = df[eval_cols].astype("string").fillna("").agg(" ".join, axis=1)
    out = pd.DataFrame({
        "REFERENCIA": limpiar_codigo(df[c_ref]),
        "COD_INTERNO": df[c_int].astype("string").fillna("").str.strip().astype(str) if c_int else "",
        "DESCRIPCION": df[c_nom].astype("string").fillna("").str.strip().astype(str) if c_nom else "",
        "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
        "EAN": df[c_ean].astype("string").fillna("").str.replace(r"\D", "", regex=True).astype(str) if c_ean else "",
        "COSTO": to_num(df[c_cos]).fillna(0) if c_cos else 0,
        "PRECIO": to_num(df[c_pre]).fillna(0) if c_pre else 0,
        "ASTERISCO": tipo_asterisco(texto_eval),
    })
    out = out[out["REFERENCIA"] != ""].copy()
    out["VALIDA"] = out["ASTERISCO"] == ""
    out["K_REF"] = clave(out["REFERENCIA"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True) if c_lot else "SIN LOTE"
    out.attrs["col_lote"] = c_lot or "(sin columna de lote: se evaluó la referencia)"
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Leyendo archivo de pistoleo…")
def leer_pistoleo(data: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith((".csv", ".txt")):
        candidatos = {"CSV": leer_csv_flexible(data, header=None)}
    else:
        xls = pd.ExcelFile(io.BytesIO(data))
        orden = sorted(xls.sheet_names, key=lambda n: (0 if norm(n) in ("INVENTARIO", "PISTOLEO", "CONTEO") else 1))
        orden = [n for n in orden if norm(n) not in ("MAESTRO", "BATCHMAESTRO", "RESUMEN")]
        candidatos = {n: pd.read_excel(xls, sheet_name=n, header=None, dtype=object) for n in orden[:4]}
    for hoja, raw in candidatos.items():
        h = detectar_encabezado(raw, {"REFERENCIA", "EAN", "ITEMNUMBER", "CODIGO"}, {"LOTE", "CANTIDAD", "BATCHNUMBER"})
        if h is None:
            continue
        df = raw.iloc[h + 1:].copy()
        df.columns = unicos(raw.iloc[h].tolist())
        df = df.dropna(how="all")
        c_ean = find_col(df, "EAN", "GTIN", "CODIGO BARRAS", parcial=False)
        c_ref = find_col(df, "REFERENCIA", "Item number", "CODIGO", parcial=False)
        c_lot = find_col(df, "LOTE", "Batch number", parcial=False)
        c_qty = find_col(df, "CANTIDAD", "CANT", "QTY", parcial=False)
        c_des = find_col(df, "DESCRIPCION", "Product name", "NOMBRE", parcial=False)
        c_ven = find_col(df, "VENCIMIENTO", "Expiration date", "FECHA VENCIMIENTO", parcial=False)
        c_gon = find_col(df, "GONDOLA", "UBICACION", "ZONA", parcial=False)
        c_niv = find_col(df, "NIVEL", parcial=False)
        c_fh = find_col(df, "FECHA_HORA REGISTRO", "FECHA HORA REGISTRO", "FECHA", parcial=True)
        c_ser = find_col(df, "SERIAL", parcial=False)
        out = pd.DataFrame({
            "EAN": df[c_ean].astype("string").fillna("").str.strip().astype(str) if c_ean else "",
            "GONDOLA": df[c_gon].astype("string").fillna("").str.strip().astype(str) if c_gon else "",
            "NIVEL": df[c_niv].astype("string").fillna("").str.strip().astype(str) if c_niv else "",
            "REFERENCIA": limpiar_codigo(df[c_ref]) if c_ref else "",
            "DESCRIPCION": df[c_des].astype("string").fillna("").str.strip().astype(str) if c_des else "",
            "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
            "VENCE": parse_fecha(df[c_ven]) if c_ven else pd.NaT,
            "CANTIDAD": to_num(df[c_qty]) if c_qty else np.nan,
            "SERIAL": limpiar_codigo(df[c_ser]) if c_ser else "",
            "FECHA_REG": df[c_fh].astype("string").fillna("").astype(str) if c_fh else "",
        })
        out = out[(out["REFERENCIA"] != "") | (out["EAN"] != "")].copy()
        out["CANTIDAD"] = out["CANTIDAD"].fillna(1)
        out["ARCHIVO"] = nombre
        out["HOJA"] = hoja
        return out.reset_index(drop=True)
    return pd.DataFrame(columns=["EAN", "GONDOLA", "NIVEL", "REFERENCIA", "DESCRIPCION", "LOTE", "VENCE",
                                 "CANTIDAD", "SERIAL", "FECHA_REG", "ARCHIVO", "HOJA"])


@st.cache_data(show_spinner="Cargando maestros Smith (GTIN y lotes) del archivo de pistoleo…")
def leer_maestros_tpn(data: bytes):
    """Devuelve (mapa GTIN->referencia, DataFrame de lotes Smith) si el archivo trae esas hojas."""
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
    except Exception:
        return {}, pd.DataFrame()
    nombres = {norm(n): n for n in xls.sheet_names}
    gtin = {}
    if "MAESTRO" in nombres:
        m = pd.read_excel(xls, sheet_name=nombres["MAESTRO"], dtype=str)
        c_it = find_col(m, "Item number", "REFERENCIA")
        for cg in [find_col(m, "GTIN", parcial=False), find_col(m, "EAN/UPC", "EAN", parcial=False)]:
            if cg and c_it:
                k = m[cg].astype("string").fillna("").str.replace(r"\D", "", regex=True).str.lstrip("0")
                v = limpiar_codigo(m[c_it])
                gtin.update({a: b for a, b in zip(k, v) if a and b})
    lotes = pd.DataFrame()
    if "BATCHMAESTRO" in nombres:
        b = pd.read_excel(xls, sheet_name=nombres["BATCHMAESTRO"], dtype=str)
        c_b = find_col(b, "Batch number", "LOTE")
        c_i = find_col(b, "Item number", "REFERENCIA")
        c_s = find_col(b, "Batch disposition status", "Estado")
        if c_b and c_i:
            lotes = pd.DataFrame({
                "K_REF": clave(limpiar_codigo(b[c_i])),
                "K_LOTE": clave(limpiar_lote(b[c_b]), es_lote=True),
                "ESTADO_LOTE": b[c_s].astype("string").fillna("").astype(str) if c_s else "",
            }).drop_duplicates(["K_REF", "K_LOTE"])
    return gtin, lotes


def conciliar_com_lot(nal_f: pd.DataFrame) -> pd.DataFrame:
    """COM = total del componente en el serial; debe ser igual a la suma de sus filas LOT."""
    com = nal_f[nal_f["TIP"] == "COM"].groupby(["SERIAL", "K_REF"], as_index=False).agg(
        BODEGA=("BOD_PROP", "first"), SET=("SET_NOMBRE", "first"), REFERENCIA=("CODIGO", "first"),
        DESCRIPCION=("NOMBRE", "first"), CANT_COM=("CANT", "sum"))
    lot = nal_f[nal_f["TIP"] == "LOT"].groupby(["SERIAL", "K_REF"], as_index=False).agg(
        BODEGA_L=("BOD_PROP", "first"), SET_L=("SET_NOMBRE", "first"), REFERENCIA_L=("CODIGO", "first"),
        DESCRIPCION_L=("NOMBRE", "first"), SUMA_LOT=("CANT", "sum"), N_LOTES=("K_LOTE", "nunique"))
    m = com.merge(lot, on=["SERIAL", "K_REF"], how="outer")
    for a, b in [("BODEGA", "BODEGA_L"), ("SET", "SET_L"), ("REFERENCIA", "REFERENCIA_L"), ("DESCRIPCION", "DESCRIPCION_L")]:
        m[a] = m[a].fillna(m[b])
    m = m.drop(columns=["BODEGA_L", "SET_L", "REFERENCIA_L", "DESCRIPCION_L"])
    m[["CANT_COM", "SUMA_LOT", "N_LOTES"]] = m[["CANT_COM", "SUMA_LOT", "N_LOTES"]].fillna(0)
    m["DIF_COM_LOT"] = m["SUMA_LOT"] - m["CANT_COM"]
    m["CUADRA"] = np.where(m["DIF_COM_LOT"] == 0, "Sí", "No")
    return m


def para_excel(df: pd.DataFrame, quitar=("K_REF", "K_LOTE", "ID", "REVISADA")) -> pd.DataFrame:
    d = df.drop(columns=[c for c in quitar if c in df.columns]).copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.tz_localize(None) if getattr(d[c].dt, "tz", None) else d[c]
        elif d[c].dtype == "object" or str(d[c].dtype).startswith("string") or str(d[c].dtype) == "str":
            d[c] = d[c].astype("object").where(d[c].notna(), "")
            d[c] = d[c].map(lambda x: EMOJI.sub("", x).strip() if isinstance(x, str) else x)
    d = d.rename(columns=NOMBRES)
    d.columns = unicos(list(d.columns))
    return d


def a_excel(hojas: dict, titulo: str, subtitulo: str = "") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as xw:
        wb = xw.book
        f_tit = wb.add_format({"bold": True, "font_size": 15, "font_color": C["navy"]})
        f_sub = wb.add_format({"italic": True, "font_size": 9, "font_color": "#5A6B85"})
        f_hdr = wb.add_format({"bold": True, "bg_color": C["navy"], "font_color": "#FFFFFF", "border": 1,
                               "text_wrap": True, "valign": "vcenter", "align": "center"})
        f_money = wb.add_format({"num_format": '"$" #,##0;[Red]-"$" #,##0'})
        f_int = wb.add_format({"num_format": "#,##0;[Red]-#,##0"})
        f_dec = wb.add_format({"num_format": "#,##0.0"})
        f_rojo = wb.add_format({"bg_color": "#F8D7DA", "font_color": "#842029"})
        f_ambar = wb.add_format({"bg_color": "#FFE8C2", "font_color": "#7A4B00"})
        f_verde = wb.add_format({"bg_color": "#D7F0EA", "font_color": "#145A50"})
        f_neg = wb.add_format({"font_color": "#C0392B", "bold": True})
        f_pos = wb.add_format({"font_color": "#1F5FA8", "bold": True})
        for nombre, df in hojas.items():
            hoja = re.sub(r"[\[\]\:\*\?\/\\]", "", nombre)[:31]
            if df is None or len(df) == 0:
                df = pd.DataFrame({"MENSAJE": ["Sin registros para esta sección"]})
            df = df.reset_index(drop=True)
            df.to_excel(xw, sheet_name=hoja, startrow=3, index=False)
            ws = xw.sheets[hoja]
            ws.write(0, 0, titulo, f_tit)
            ws.write(1, 0, f"{subtitulo}   ·   Generado: {ahora():%d/%m/%Y %H:%M}", f_sub)
            n, cols = len(df), list(df.columns)
            for j, c in enumerate(cols):
                ws.write(3, j, c, f_hdr)
                muestra = df[c].astype(str).head(400)
                ancho = min(max(len(str(c)) * 0.9, muestra.str.len().quantile(0.9) if n else 8) + 3, 55)
                fmt = None
                if any(k in str(c) for k in ("VALOR", "COSTO", "$")):
                    fmt = f_money
                elif pd.api.types.is_numeric_dtype(df[c]):
                    fmt = f_dec if str(c).startswith("%") or "AVANCE" in str(c) else f_int
                ws.set_column(j, j, ancho, fmt)
            ws.set_row(3, 32)
            ws.freeze_panes(4, 1 if len(cols) > 3 else 0)
            ws.autofilter(3, 0, 3 + n, len(cols) - 1)
            from xlsxwriter.utility import xl_col_to_name
            if "ESTADO VENC." in cols and n:
                L = xl_col_to_name(cols.index("ESTADO VENC."))
                ws.conditional_format(4, 0, 3 + n, len(cols) - 1,
                                      {"type": "formula", "criteria": f'=${L}5="VENCIDO"', "format": f_rojo})
                ws.conditional_format(4, 0, 3 + n, len(cols) - 1,
                                      {"type": "formula", "criteria": f'=${L}5="PRÓXIMO A VENCER"', "format": f_ambar})
            if "ESTADO" in cols and n:
                j = cols.index("ESTADO")
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "FALTANTE", "format": f_rojo})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "SOBRANTE", "format": f_ambar})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "CUADRADO", "format": f_verde})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "NO", "format": f_ambar})
            for nom_dif in ("DIFERENCIA", "DIF. (LOT - COM)"):
                if nom_dif in cols and n:
                    j = cols.index(nom_dif)
                    ws.conditional_format(4, j, 3 + n, j, {"type": "cell", "criteria": "<", "value": 0, "format": f_neg})
                    ws.conditional_format(4, j, 3 + n, j, {"type": "cell", "criteria": ">", "value": 0, "format": f_pos})
    return buf.getvalue()


def kpi(col, titulo, valor, sub="", color=C["teal"], barra=None):
    barra_html = ""
    if barra is not None:
        b = max(0.0, min(100.0, float(barra)))
        barra_html = f'<div class="bar"><div style="width:{b:.1f}%"></div></div>'
    col.markdown(f'<div class="kpi" style="--c:{color}"><div class="t">{titulo}</div>'
                 f'<div class="v">{valor}</div><div class="s">{sub}</div>{barra_html}</div>',
                 unsafe_allow_html=True)


def alerta(texto, tipo="azul"):
    st.markdown(f'<div class="alerta {tipo}">{texto}</div>', unsafe_allow_html=True)


def seccion(texto):
    st.markdown(f'<div class="seccion">{texto}</div>', unsafe_allow_html=True)


def estilo_filas(df: pd.DataFrame):
    """Resalta en rojo lo vencido y en ámbar lo próximo a vencer; colorea estados."""
    def fila(r):
        ev = r.get("ESTADO VENC.", r.get("ESTADO_VENC", ""))
        if ev == "VENCIDO":
            return ["background-color:#F8D7DA;color:#842029;font-weight:600"] * len(r)
        if ev == "PRÓXIMO A VENCER":
            return ["background-color:#FFE8C2;color:#7A4B00"] * len(r)
        return [""] * len(r)
    sty = df.style.apply(fila, axis=1)
    if "ESTADO" in df.columns:
        def est(v):
            v = str(v)
            if "FALTANTE" in v:
                return "color:#B42318;font-weight:700"
            if "SOBRANTE" in v or "NO COINCIDE" in v or "NO ESTÁ" in v:
                return "color:#B54708;font-weight:700"
            if "CUADRADO" in v:
                return "color:#067647;font-weight:700"
            return ""
        sty = sty.map(est, subset=["ESTADO"])
    fmt = {}
    for c in df.columns:
        if any(k in c for k in ("VALOR", "COSTO")):
            fmt[c] = lambda x: fmt_cop(x) if pd.notna(x) else ""
        elif c in ("VENCIMIENTO", "VENCE"):
            fmt[c] = lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else ""
        elif pd.api.types.is_float_dtype(df[c]):
            fmt[c] = lambda x: fmt_num(x) if pd.notna(x) else ""
    return sty.format(fmt)


def mostrar_tabla(df: pd.DataFrame, alto=460, limite=6000):
    if df is None or df.empty:
        st.info("Sin registros para mostrar con los filtros actuales.")
        return
    d = para_excel(df)
    if len(d) > limite:
        st.caption(f"Mostrando las primeras {fmt_num(limite)} de {fmt_num(len(d))} filas (el Excel exportado contiene todo).")
        d = d.head(limite)
    st.dataframe(estilo_filas(d), height=alto, hide_index=True)


def layout_fig(fig, alto=340, titulo=None):
    fig.update_layout(
        height=alto, margin=dict(l=10, r=10, t=50 if titulo else 20, b=10),
        title=dict(text=titulo, font=dict(size=15, color=C["navy"])) if titulo else None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial", color="#33415C"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    return fig


def logo_html() -> str:
    logo_dir = os.path.join(DIR_DATOS, "logo")
    logo = None
    for n in LOGOS_LOCALES:
        if os.path.exists(os.path.join(BASE_DIR, n)):
            logo = os.path.join(BASE_DIR, n)
            break
    if logo is None and os.path.isdir(logo_dir) and os.listdir(logo_dir):
        logo = os.path.join(logo_dir, sorted(os.listdir(logo_dir))[0])
    if logo:
        with open(logo, "rb") as fh:
            b64, mime = base64.b64encode(fh.read()).decode(), "image/jpeg" if logo.lower().endswith(("jpg", "jpeg")) else "image/png"
    else:
        b64, mime = LOGO_TECNITRAUMA_B64, "image/png"
    return f'<div class="logo-box"><img src="data:{mime};base64,{b64}" alt="Tecnitrauma"></div>'


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d\u2139\u23F0-\u23FA\u2194-\u21FF]")


NOMBRES = {
    "REFERENCIA": "REFERENCIA", "DESCRIPCION": "DESCRIPCIÓN", "LOTE": "LOTE", "VENCE": "VENCIMIENTO",
    "DIAS_VENCE": "DÍAS PARA VENCER", "ESTADO_VENC": "ESTADO VENC.", "TEORICO": "TEÓRICO (TEMPLETE)",
    "CONTADO": "CONTADO", "DIFERENCIA": "DIFERENCIA", "ESTADO": "ESTADO", "COSTO_UNIT": "COSTO UNIT.",
    "VALOR_TEORICO": "VALOR TEÓRICO", "VALOR_CONTADO": "VALOR CONTADO", "VALOR_DIF": "VALOR DIFERENCIA",
    "LOTE_EN_TEMPLETE": "LOTE EN TEMPLETE", "REF_EN_TEMPLETE": "REF. EN TEMPLETE",
    "LOTE_EN_MAESTRO_SMITH": "LOTE EN MAESTRO SMITH", "VALREF": "VALREF", "NAL_SUELTAS": "NAL SUELTAS (REF)",
    "NAL_SERIALES": "NAL EN SERIALES (LOT)", "NAL_TOTAL": "NAL TOTAL (INFORMATIVO)",
    "NAL_SERIALES_ID": "SERIALES NAL", "GONDOLAS": "GÓNDOLAS", "UBICACION": "UBICACIÓN SMITH",
    "LOTES": "N° LOTES", "LOTES_CON_DIF": "LOTES CON DIFERENCIA", "VENCIDOS": "LOTES VENCIDOS",
    "BODEGA": "BODEGA", "TIPO": "TIPO", "SERIAL": "SERIAL", "SET": "NOMBRE SET", "SISTEMA": "SISTEMA (NAL)",
    "OBSERVACION": "OBSERVACIÓN", "CONTADO_POR": "CONTADO POR", "CANT_COM": "CANT. COM",
    "SUMA_LOT": "SUMA LOT", "VALOR_SISTEMA": "VALOR SISTEMA", "LECTURAS": "LECTURAS", "MANUAL": "REG. MANUALES",
    "PAREJAS": "PAREJAS", "BODEGAS": "BODEGAS", "ORIGEN": "ORIGEN", "TEMPLETE": "TEMPLETE", "NAL": "NAL (SISTEMA)",
    "UNIDADES": "UNIDADES SISTEMA", "BODEGA_NOM": "NOMBRE BODEGA", "ORIGEN_BOD": "ORIGEN BODEGA", "CERRADO_POR": "CERRADO POR",
    "CERRADO_TS": "CERRADO", "ULTIMA": "ÚLTIMA LECTURA", "LINEAS": "LÍNEAS", "N_LOTES": "N° LOTES", "DIF_COM_LOT": "DIF. (LOT - COM)", "CUADRA": "CUADRA",
}



def logo_html() -> str:
    return f'<div class="logo-box"><img src="data:image/png;base64,{LOGO_TECNITRAUMA_B64}" alt="Tecnitrauma"></div>'


CSS_EXTRA = """
<style>
.pareja-head {background:#fff; border-radius:14px; padding:12px 18px; box-shadow:0 2px 12px rgba(11,37,69,.08);
  border-left:6px solid #2A88C9; margin-bottom:10px;}
.pareja-head b {color:#0B2545; font-size:1.15rem;}
.ok-scan {background:#E8F6F3; border-left:6px solid #2A9D8F; padding:12px 16px; border-radius:10px; font-size:1.05rem; color:#145A50;}
.rev-scan {background:#FFF6D6; border-left:6px solid #E0B000; padding:12px 16px; border-radius:10px; font-size:1.05rem; color:#6B5200;}
.no-scan {background:#FDECEC; border-left:6px solid #D64545; padding:12px 16px; border-radius:10px; font-size:1.05rem; color:#7A1F1F;}
div[data-testid="stForm"] {background:#FFFFFF; border-radius:14px;}
</style>
"""

# =============================================================================
# BASE DE DATOS (Supabase/PostgreSQL en la nube  ·  SQLite en local)
# =============================================================================
META = MetaData()
T_LECT = Table(
    "lecturas", META,
    Column("id", String(24), primary_key=True), Column("ts", String(19)), Column("pareja", String(80)),
    Column("auxiliares", String(200)), Column("modo", String(12)), Column("grupo", String(10)),
    Column("zona", String(60)), Column("gondola", String(40)), Column("nivel", String(20)),
    Column("serial", String(60)), Column("codigo_leido", String(300)), Column("referencia", String(80)),
    Column("descripcion", String(250)), Column("lote", String(80)), Column("vence", String(10)),
    Column("cantidad", Float), Column("observacion", String(400)), Column("origen", String(120)),
    Column("anulada", Integer, default=0), Column("anulada_por", String(80)), Column("anulada_ts", String(19)))
T_PAR = Table(
    "parejas", META,
    Column("id", String(12), primary_key=True), Column("nombre", String(80)), Column("aux1", String(80)),
    Column("aux2", String(80)), Column("pin", String(8)), Column("zona", String(60)), Column("gondolas", String(200)),
    Column("estado", String(12)), Column("inicio", String(19)), Column("fin", String(19)))
T_SER = Table(
    "seriales_estado", META,
    Column("serial", String(60), primary_key=True), Column("grupo", String(10)), Column("estado", String(12)),
    Column("pareja", String(80)), Column("ts", String(19)))
T_MAE = Table(
    "maestros", META,
    Column("tipo", String(20), primary_key=True), Column("nombre", String(200)), Column("sha", String(64)),
    Column("ts", String(19)), Column("tam", Integer), Column("datos", LargeBinary))
T_CFG = Table("config", META, Column("k", String(60), primary_key=True), Column("v", Text))
T_OBS = Table(
    "observaciones", META,
    Column("id", String(200), primary_key=True), Column("grupo", String(10)), Column("nivel", String(10)),
    Column("k_ref", String(80)), Column("k_lote", String(80)), Column("observacion", Text),
    Column("conciliacion", String(40)), Column("usuario", String(80)), Column("ts", String(19)))
T_COR = Table(
    "correcciones", META,
    Column("id", String(24), primary_key=True), Column("lectura_id", String(24)), Column("ts", String(19)),
    Column("usuario", String(80)), Column("campo", String(40)), Column("antes", String(300)), Column("despues", String(300)))


def _secreto(nombre: str, defecto: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, defecto) or defecto)
    except Exception:
        return defecto


@st.cache_resource(show_spinner="Conectando con la base de datos…")
def motor():
    url = _secreto("DB_URL")
    if url:
        url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", url)
        eng = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=280, pool_timeout=10,
                            connect_args={"connect_timeout": 5, "keepalives": 1, "keepalives_idle": 30,
                                          "keepalives_interval": 10, "keepalives_count": 3})
        modo = "nube"
    else:
        os.makedirs(DIR_DATOS, exist_ok=True)
        eng = create_engine("sqlite:///" + os.path.join(DIR_DATOS, "inventario.db"),
                            connect_args={"check_same_thread": False, "timeout": 30})
        with eng.begin() as c:
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
        modo = "local"
    META.create_all(eng)
    return eng, modo


def bd():
    return motor()[0]


def ejecutar(stmt, filas=None):
    with bd().begin() as c:
        if filas is None:
            c.execute(stmt)
        else:
            c.execute(stmt, filas)


def consultar(stmt) -> pd.DataFrame:
    with bd().connect() as c:
        return pd.read_sql(stmt, c)


@st.cache_data(ttl=10, show_spinner=False)
def config_todo() -> dict:
    df = consultar(select(T_CFG))
    return dict(zip(df["k"], df["v"]))


def cfg(k, defecto=None):
    return config_todo().get(k, defecto)


def cfg_set(k, v):
    with bd().begin() as c:
        c.execute(delete(T_CFG).where(T_CFG.c.k == k))
        c.execute(insert(T_CFG).values(k=k, v=str(v)))
    config_todo.clear()


@st.cache_data(ttl=2, show_spinner=False)
def version_datos() -> str:
    """Huella barata de los datos de conteo: si no cambia, no se vuelve a descargar nada."""
    from sqlalchemy import func
    with bd().connect() as c:
        a = c.execute(select(func.count(), func.max(T_LECT.c.ts), func.sum(T_LECT.c.anulada),
                             func.max(T_LECT.c.anulada_ts))).one()
        b = c.execute(select(func.count(), func.max(T_COR.c.ts))).one()
        d = c.execute(select(func.count(), func.max(T_SER.c.ts))).one()
    return f"{a[0]}|{a[1]}|{a[2]}|{a[3]}|{b[0]}|{b[1]}|{d[0]}|{d[1]}"


@st.cache_data(max_entries=3, show_spinner=False)
def _lecturas_por_version(version: str) -> pd.DataFrame:
    df = consultar(select(T_LECT))
    if df.empty:
        return df
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
    df["anulada"] = pd.to_numeric(df["anulada"], errors="coerce").fillna(0).astype(int)
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith(("str", "string")):
            df[c] = df[c].fillna("").astype(str)
    return df


def leer_lecturas() -> pd.DataFrame:
    return _lecturas_por_version(version_datos())


leer_lecturas.clear = lambda: version_datos.clear()


@st.cache_data(max_entries=200, show_spinner=False)
def _lecturas_pareja(pareja: str, version: str) -> pd.DataFrame:
    """Solo las lecturas de una pareja (consulta liviana para la pantalla de conteo)."""
    df = consultar(select(T_LECT).where(T_LECT.c.pareja == pareja))
    if df.empty:
        return df
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
    df["anulada"] = pd.to_numeric(df["anulada"], errors="coerce").fillna(0).astype(int)
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith(("str", "string")):
            df[c] = df[c].fillna("").astype(str)
    return df


def lecturas_de_pareja(pareja: str) -> pd.DataFrame:
    return _lecturas_pareja(pareja, version_datos())


@st.cache_data(max_entries=3, show_spinner=False)
def _resumen_seriales_por_version(version: str) -> pd.DataFrame:
    """Lecturas agregadas por serial (para saber qué seriales están en conteo) sin bajar toda la tabla."""
    from sqlalchemy import func
    q = (select(T_LECT.c.serial, T_LECT.c.pareja, func.count().label("n"), func.sum(T_LECT.c.cantidad).label("u"),
                func.max(T_LECT.c.ts).label("ult"))
         .where(T_LECT.c.anulada == 0).where(T_LECT.c.serial != "").group_by(T_LECT.c.serial, T_LECT.c.pareja))
    return consultar(q)


def resumen_seriales() -> pd.DataFrame:
    return _resumen_seriales_por_version(version_datos())


@st.cache_data(ttl=4, show_spinner=False)
def leer_parejas() -> pd.DataFrame:
    return consultar(select(T_PAR)).fillna("")


@st.cache_data(ttl=4, show_spinner=False)
def leer_estado_seriales() -> pd.DataFrame:
    return consultar(select(T_SER)).fillna("")


@st.cache_data(ttl=30, show_spinner=False)
def maestros_meta() -> pd.DataFrame:
    return consultar(select(T_MAE.c.tipo, T_MAE.c.nombre, T_MAE.c.sha, T_MAE.c.ts, T_MAE.c.tam))


@st.cache_data(max_entries=8, show_spinner="Descargando archivo maestro…")
def bytes_maestro(tipo: str, sha: str) -> bytes:
    df = consultar(select(T_MAE.c.datos).where(T_MAE.c.tipo == tipo))
    return gzip.decompress(bytes(df["datos"].iloc[0])) if len(df) else b""


def guardar_maestro(tipo: str, nombre: str, data: bytes):
    sha = hashlib.sha256(data).hexdigest()
    with bd().begin() as c:
        c.execute(delete(T_MAE).where(T_MAE.c.tipo == tipo))
        c.execute(insert(T_MAE).values(tipo=tipo, nombre=nombre, sha=sha, ts=ahora().strftime("%Y-%m-%d %H:%M:%S"),
                                       tam=len(data), datos=gzip.compress(data, 6)))
    maestros_meta.clear()


def limpiar_caches_conteo():
    leer_lecturas.clear()
    leer_parejas.clear()
    leer_estado_seriales.clear()
    for fn in ("leer_correcciones", "leer_observaciones"):
        try:
            globals()[fn].clear()
        except Exception:
            pass


def _insertar_idempotente(fila: dict):
    """Inserta una lectura; si ya existe (reintento de la misma lectura) no la duplica."""
    from sqlalchemy.exc import IntegrityError
    cols = {c.name for c in T_LECT.columns}
    try:
        ejecutar(insert(T_LECT).values(**{k: v for k, v in fila.items() if k in cols}))
    except IntegrityError:
        pass   # ya estaba guardada: el reintento no duplica


def _con_reintentos(fn, intentos: int = 3):
    import time as _t
    from sqlalchemy.exc import IntegrityError
    ultimo = None
    for k in range(intentos):
        try:
            return fn()
        except IntegrityError:
            raise
        except Exception as e:      # caída de red / conexión reciclada: reintentar
            ultimo = e
            try:
                bd().dispose()
            except Exception:
                pass
            _t.sleep(0.3 * (k + 1))
    raise ultimo


def vaciar_cola_pendiente() -> int:
    """Reintenta guardar lecturas que no se pudieron grabar (sin conexión). Devuelve cuántas quedan."""
    cola = st.session_state.get("cola_pendiente", [])
    if not cola:
        return 0
    quedan = []
    for fila in cola:
        try:
            _con_reintentos(lambda f=fila: _insertar_idempotente(f), intentos=2)
        except Exception:
            quedan.append(fila)
    st.session_state["cola_pendiente"] = quedan
    if not quedan:
        st.session_state["bd_caida_ts"] = 0
    if len(quedan) < len(cola):
        leer_lecturas.clear()
    return len(quedan)


def registrar_lectura(**kw):
    """Guarda una lectura con reintentos. Si la base no responde, la deja en cola y la reintenta sola:
    nunca se pierde lo pistoleado."""
    fila = {c.name: "" for c in T_LECT.columns}
    fila.update(id=uuid.uuid4().hex[:16], ts=ahora().strftime("%Y-%m-%d %H:%M:%S"), anulada=0, cantidad=1.0)
    fila.update({k: v for k, v in kw.items() if k in fila})
    fila["cantidad"] = float(fila["cantidad"] or 0)
    import time as _t
    caida = st.session_state.get("bd_caida_ts", 0)
    if caida and _t.time() - caida < 8:
        # La base acaba de fallar: se guarda en el equipo sin hacer esperar a la pareja
        st.session_state.setdefault("cola_pendiente", []).append(dict(fila))
        fila["_guardada"] = False
        return fila
    try:
        _con_reintentos(lambda: _insertar_idempotente(fila))
        fila["_guardada"] = True
        st.session_state["bd_caida_ts"] = 0
    except Exception:
        st.session_state.setdefault("cola_pendiente", []).append(dict(fila))
        st.session_state["bd_caida_ts"] = _t.time()
        fila["_guardada"] = False
    leer_lecturas.clear()
    return fila


def anular_lecturas(ids, por: str):
    if not ids:
        return
    _con_reintentos(lambda: ejecutar(update(T_LECT).where(T_LECT.c.id.in_(list(ids))).values(
        anulada=1, anulada_por=por, anulada_ts=ahora().strftime("%Y-%m-%d %H:%M:%S"))))
    leer_lecturas.clear()


# ---- Observaciones de conciliación (por referencia o por referencia + lote)
@st.cache_data(ttl=30, show_spinner=False)
def leer_observaciones() -> pd.DataFrame:
    return consultar(select(T_OBS)).fillna("")


def guardar_observaciones(cambios: list, usuario: str):
    """cambios = [dict(grupo, nivel, k_ref, k_lote, observacion, conciliacion)]"""
    if not cambios:
        return
    ts = ahora().strftime("%Y-%m-%d %H:%M:%S")
    def _tx():
        with bd().begin() as c:
            for o in cambios:
                oid = f"{o['grupo']}|{o['nivel']}|{o['k_ref']}|{o.get('k_lote', '')}"[:200]
                c.execute(delete(T_OBS).where(T_OBS.c.id == oid))
                if str(o.get("observacion", "")).strip() or str(o.get("conciliacion", "")).strip() not in ("", "Sin revisar"):
                    c.execute(insert(T_OBS).values(id=oid, grupo=o["grupo"], nivel=o["nivel"], k_ref=o["k_ref"],
                                                   k_lote=o.get("k_lote", ""), observacion=str(o.get("observacion", "")).strip(),
                                                   conciliacion=o.get("conciliacion", "") or "Sin revisar",
                                                   usuario=usuario, ts=ts))
    _con_reintentos(_tx)
    leer_observaciones.clear()


def fijar_estado_serial(serial: str, grupo: str, estado: str | None, pareja: str = ""):
    with bd().begin() as c:
        c.execute(delete(T_SER).where(T_SER.c.serial == serial))
        if estado:
            c.execute(insert(T_SER).values(serial=serial, grupo=grupo, estado=estado, pareja=pareja,
                                           ts=ahora().strftime("%Y-%m-%d %H:%M:%S")))
    leer_estado_seriales.clear()

# =============================================================================
# CLAVES
# =============================================================================

def _hash(clave: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal.encode("utf-8"), 100_000).hex()


def verificar_admin(clave: str) -> bool:
    h, sal = cfg("admin_hash"), cfg("admin_sal")
    if h and sal:
        return _hash(clave, sal) == h
    return clave == _secreto("CLAVE_ADMIN", CLAVE_ADMIN_INICIAL)


def cambiar_clave_admin(nueva: str):
    sal = uuid.uuid4().hex
    cfg_set("admin_sal", sal)
    cfg_set("admin_hash", _hash(nueva, sal))

# =============================================================================
# PARÁMETROS
# =============================================================================

def parametros() -> dict:
    return dict(
        criterio=cfg("criterio", "Propietaria (BODEGA PROPIE.)"),
        incluir_otras=cfg("incluir_otras", "1") == "1",
        dias=int(cfg("dias", "90")),
        base_valor=cfg("base_valor", "Costo promedio (Valref)"),
        cliente=cfg("cliente", "Smith & Nephew"),
        responsable=cfg("responsable", ""),
        hoja_tpl=cfg("hoja_tpl", ""),
        hoja_ser=cfg("hoja_ser", ""),
        solo_implantes=cfg("solo_implantes", "1") == "1",
        avisos_pareja=cfg("avisos_pareja", "0") == "1",
    )

# =============================================================================
# UNIVERSO A CONTAR (desde el NAL)
# =============================================================================

def sha_de(tipo: str) -> str:
    m = maestros_meta()
    r = m[m["tipo"] == tipo]
    return r["sha"].iloc[0] if len(r) else ""


def nombre_de(tipo: str) -> str:
    m = maestros_meta()
    r = m[m["tipo"] == tipo]
    return r["nombre"].iloc[0] if len(r) else ""


@st.cache_data(max_entries=3, show_spinner="Leyendo Valref…")
def valref_df(sha: str):
    if not sha:
        return None
    return leer_valref(bytes_maestro("valref", sha), nombre_de("valref") or "valref.csv")


@st.cache_data(max_entries=3, show_spinner="Leyendo Templete…")
def templete_df(sha: str, hoja: str):
    if not sha:
        return None
    return leer_templete(bytes_maestro("templete", sha), nombre_de("templete") or "templete.xlsx", hoja or None)


@st.cache_data(max_entries=3, show_spinner="Leyendo templete de Serena del Mar…")
def serena_tpl_df(sha: str, hoja: str):
    if not sha:
        return None
    return leer_templete(bytes_maestro("serena", sha), nombre_de("serena") or "serena.xlsx", hoja or None)


@st.cache_data(max_entries=3, show_spinner="Leyendo maestros GTIN y lotes Smith…")
def maestros_smith(sha_tpn: str, sha_val: str):
    gtin, lotes = ({}, pd.DataFrame())
    if sha_tpn:
        gtin, lotes = leer_maestros_tpn(bytes_maestro("tpn", sha_tpn))
        gtin = dict(gtin)
    v = valref_df(sha_val)
    if v is not None:
        for ean, ref in zip(v["EAN"], v["REFERENCIA"]):
            if ean and ref:
                gtin.setdefault(ean.lstrip("0"), ref)
    return gtin, lotes


@st.cache_data(max_entries=3, show_spinner="Preparando el inventario a contar (NAL)…")
def construir_universo(sha_nal: str, sha_val: str, criterio: str, incluir_otras: bool, dias: int,
                       sha_tpl: str = "", hoja_tpl: str = "", sha_ser: str = "", hoja_ser: str = "",
                       solo_implantes: bool = True):
    """Líneas a contar (stock y seriales), seriales, fuera de alcance (asteriscos / instrumental / no en templete)
    y conciliación Com/Lot."""
    vacio = dict(U=pd.DataFrame(), S=pd.DataFrame(), excl=pd.DataFrame(), conc=pd.DataFrame(), info={}, neg=pd.DataFrame(),
                 implantes=set(), instrumental=set(), ast_refs=set(), ast_pares=set())
    if not sha_nal:
        return vacio
    nal = leer_nal(bytes_maestro("nal", sha_nal)).copy()
    val = valref_df(sha_val)
    col = "BOD_PROP" if criterio.startswith("Propietaria") else "BOD_EXIST"
    col_nom = "BOD_PROP_NOM" if col == "BOD_PROP" else "BOD_EXIST_NOM"
    b = nal[col]
    es_smith, es_serena = b.isin(BODEGAS_SMITH), b.isin(BODEGAS_SERENA)
    validas = set(val.loc[val["VALIDA"], "K_REF"]) if val is not None else set()
    asteriscos = tiene_asterisco(nal["CODIGO"]) | tiene_asterisco(nal["LOTE"])
    # Seriales de las bodegas de equipos de cada ciudad (02, 10, 20, 27, 33 por BODEGA PROPIETARIA):
    # se cuentan los lotes de las referencias que están en el templete Smith (si no hay templete: en Valref),
    # siempre que el código o el lote NO tenga * ni ** (regla aplicada solo al NAL).
    bp = nal["BOD_PROP"]
    T0 = templete_df(sha_tpl, hoja_tpl) if sha_tpl else None
    refs_ok = set(T0["K_REF"]) if T0 is not None and not T0.empty else validas
    candidata = (~es_smith & ~es_serena & bp.isin(BODEGAS_EQUIPOS_CIUDAD)
                 & (nal["TIP"] == "LOT") & (nal["SERIAL"] != "") & nal["K_REF"].isin(refs_ok))
    if not incluir_otras:
        candidata = candidata & False
    otras = candidata & ~asteriscos
    nal["GRUPO"] = np.select([es_serena, es_smith, otras], ["SERENA", "SMITH", "SMITH"], "")
    nal["ORIGEN_BOD"] = np.select([es_serena, es_smith, otras], ["Bodega Serena", "Bodega Smith", "Serial equipos ciudad"], "")
    nal["BODEGA"] = np.where(otras, bp, b)
    nal["BODEGA_NOM"] = np.where(otras, nal["BOD_PROP_NOM"], nal[col_nom])
    excl = nal[candidata & asteriscos].copy()
    excl["GRUPO"] = "SMITH"
    excl["ORIGEN_BOD"] = "Serial equipos ciudad"
    excl["BODEGA_NOM"] = excl["BOD_PROP_NOM"]
    excl["MOTIVO"] = "Lote o código con * / ** en el NAL (serial de equipos ciudad)"
    base = nal[nal["GRUPO"] != ""].copy()
    # ---- Alcance por templete: Smith = solo IMPLANTES del templete (el instrumental no se cuenta);
    #      Serena del Mar = solo referencias de su propio templete.
    motivo = pd.Series("", index=base.index, dtype=object)
    es_item = base["TIP"].isin(["REF", "LOT", "COM"])
    implantes, instrumental = set(), set()
    T = templete_df(sha_tpl, hoja_tpl) if sha_tpl else None
    if T is not None and not T.empty:
        implantes = set(T.loc[T["CLASE"] == "IMPLANTE", "K_REF"])
        instrumental = set(T.loc[T["CLASE"] == "INSTRUMENTAL", "K_REF"]) - implantes
        if solo_implantes:
            m = es_item & (base["GRUPO"] == "SMITH") & ~base["K_REF"].isin(implantes)
            motivo[m] = np.where(base.loc[m, "K_REF"].isin(instrumental), "Instrumental (CAP en templete Smith)",
                                 "Instrumental / no está en templete Smith")
    TS = serena_tpl_df(sha_ser, hoja_ser) if sha_ser else None
    if TS is not None and not TS.empty:
        m = es_item & (base["GRUPO"] == "SERENA") & ~base["K_REF"].isin(set(TS["K_REF"]))
        motivo[m] = "No está en templete Serena del Mar"
    fuera = base[motivo != ""].copy()
    fuera["MOTIVO"] = motivo[motivo != ""]
    base = base[motivo == ""].copy()
    excl = pd.concat([excl, fuera], ignore_index=True)
    # Marcas * / ** (en el código o el lote del NAL completo y en Valref): esas referencias/lotes no se cuentan
    ast_n = nal[asteriscos]
    ast_refs = set(ast_n.loc[tiene_asterisco(ast_n["CODIGO"]), "K_REF"])
    ast_pares = set(zip(ast_n.loc[tiene_asterisco(ast_n["LOTE"]), "K_REF"], ast_n.loc[tiene_asterisco(ast_n["LOTE"]), "K_LOTE"]))
    if val is not None:
        va = val[~val["VALIDA"]]
        if va["LOTE"].ne("").any():
            ast_pares |= set(zip(va["K_REF"], va["K_LOTE"]))
        else:
            ast_refs |= set(va["K_REF"])
    # Un serial pertenece al grupo de su fila SET (si existe) para no partir kits
    grupo_serial = base[base["SERIAL"] != ""].groupby("SERIAL")["GRUPO"].first()
    ref = base[base["TIP"] == "REF"]
    lot = base[base["TIP"] == "LOT"]
    partes = [
        pd.DataFrame({"GRUPO": ref["GRUPO"], "ORIGEN_BOD": ref["ORIGEN_BOD"], "BODEGA": ref["BODEGA"],
                      "BODEGA_NOM": ref["BODEGA_NOM"], "TIPO": "STOCK", "SERIAL": "", "SET": "",
                      "REFERENCIA": ref["CODIGO"], "DESCRIPCION": ref["NOMBRE"], "LOTE": ref["LOTE"],
                      "VENCE": ref["VENCE"], "SISTEMA": ref["CANT"], "K_REF": ref["K_REF"]}),
        pd.DataFrame({"GRUPO": lot["GRUPO"], "ORIGEN_BOD": lot["ORIGEN_BOD"], "BODEGA": lot["BODEGA"],
                      "BODEGA_NOM": lot["BODEGA_NOM"], "TIPO": "SERIAL", "SERIAL": lot["SERIAL"],
                      "SET": lot["SET_NOMBRE"], "REFERENCIA": lot["CODIGO"], "DESCRIPCION": lot["NOMBRE"],
                      "LOTE": lot["LOTE"], "VENCE": lot["VENCE"], "SISTEMA": lot["CANT"], "K_REF": lot["K_REF"]}),
    ]
    conc = conciliar_com_lot(base)
    if not conc.empty:
        info_ser = base[base["SERIAL"] != ""].groupby("SERIAL").agg(
            GRUPO=("GRUPO", "first"), ORIGEN_BOD=("ORIGEN_BOD", "first"), BODEGA_X=("BODEGA", "first"),
            BODEGA_NOM=("BODEGA_NOM", "first"))
        conc = conc.merge(info_ser, left_on="SERIAL", right_index=True, how="left")
        sin_lote = conc[conc["CANT_COM"] > conc["SUMA_LOT"]]
        if not sin_lote.empty:
            partes.append(pd.DataFrame({
                "GRUPO": sin_lote["GRUPO"], "ORIGEN_BOD": sin_lote["ORIGEN_BOD"], "BODEGA": sin_lote["BODEGA_X"],
                "BODEGA_NOM": sin_lote["BODEGA_NOM"], "TIPO": "SERIAL", "SERIAL": sin_lote["SERIAL"],
                "SET": sin_lote["SET"], "REFERENCIA": sin_lote["REFERENCIA"], "DESCRIPCION": sin_lote["DESCRIPCION"],
                "LOTE": "SIN LOTE", "VENCE": pd.NaT, "SISTEMA": sin_lote["CANT_COM"] - sin_lote["SUMA_LOT"],
                "K_REF": sin_lote["K_REF"]}))
    U = pd.concat(partes, ignore_index=True)
    U["SERIAL"] = U["SERIAL"].fillna("").astype(str)
    U.loc[U["SERIAL"] != "", "GRUPO"] = U.loc[U["SERIAL"] != "", "SERIAL"].map(grupo_serial).fillna(U["GRUPO"])
    U["LOTE"] = U["LOTE"].fillna("").astype(str).replace("", "SIN LOTE")
    U["K_LOTE"] = clave(U["LOTE"], es_lote=True)
    U["BODEGA"] = pd.to_numeric(U["BODEGA"], errors="coerce").fillna(0).astype(int)
    U["VENCE"] = pd.to_datetime(U["VENCE"])
    U["SISTEMA"] = pd.to_numeric(U["SISTEMA"], errors="coerce").fillna(0)
    negativos = U[U["SISTEMA"] < 0].copy()
    U = U[U["SISTEMA"] > 0].copy()
    if val is not None:
        v = val.drop_duplicates("K_REF").set_index("K_REF")
        U["COSTO"] = U["K_REF"].map(v["COSTO"]).fillna(0)
        U["PRECIO"] = U["K_REF"].map(v["PRECIO"]).fillna(0)
    else:
        U["COSTO"], U["PRECIO"] = 0.0, 0.0
    U["DIAS_VENCE"], U["ESTADO_VENC"] = estado_venc(U["VENCE"], dias)
    sets = base[base["TIP"] == "SET"].drop_duplicates("SERIAL").set_index("SERIAL")
    S = U[U["TIPO"] == "SERIAL"].groupby("SERIAL", as_index=False).agg(
        GRUPO=("GRUPO", "first"), SET=("SET", "first"), BODEGA=("BODEGA", "first"), BODEGA_NOM=("BODEGA_NOM", "first"),
        ORIGEN_BOD=("ORIGEN_BOD", "first"), LINEAS=("REFERENCIA", "count"), UNIDADES=("SISTEMA", "sum"),
        REFERENCIAS=("K_REF", "nunique"))
    S["SET"] = S["SET"].where(S["SET"] != "", S["SERIAL"].map(sets["NOMBRE"]).fillna(""))
    info = {
        "lineas": len(U), "seriales": len(S),
        "stock_smith": float(U.loc[(U["GRUPO"] == "SMITH") & (U["TIPO"] == "STOCK"), "SISTEMA"].sum()),
        "excluidos_ast": int(excl["MOTIVO"].astype(str).str.contains("*", regex=False).sum()), "otras_bodegas": int((U["ORIGEN_BOD"] == "Serial equipos ciudad").sum()),
        "seriales_otras": int(U.loc[U["ORIGEN_BOD"] == "Serial equipos ciudad", "SERIAL"].nunique()),
        "descuadres_com_lot": int((conc["CUADRA"] == "No").sum()) if not conc.empty else 0,
        "negativos": len(negativos),
        "fuera_alcance": len(excl), "instrumental_lineas": int(excl["MOTIVO"].astype(str).str.startswith("Instrumental").sum()),
        "smith_tpl": T is not None and not T.empty, "serena_tpl": TS is not None and not TS.empty,
        "seriales_smith": int(S.loc[S["GRUPO"] == "SMITH", "SERIAL"].nunique()) if not S.empty else 0,
        "seriales_serena": int(S.loc[S["GRUPO"] == "SERENA", "SERIAL"].nunique()) if not S.empty else 0,
    }
    excl_v = excl[["GRUPO", "MOTIVO", "ORIGEN_BOD", "BODEGA_NOM", "TIP", "SERIAL", "SET_NOMBRE", "CODIGO", "NOMBRE",
                   "LOTE", "CANT"]].rename(columns={"SET_NOMBRE": "SET", "CODIGO": "REFERENCIA", "NOMBRE": "DESCRIPCION",
                                                    "CANT": "CANTIDAD", "TIP": "TIPO_NAL"})
    return dict(U=U.reset_index(drop=True), S=S, excl=excl_v, conc=conc, info=info, implantes=implantes,
                instrumental=instrumental, ast_refs=ast_refs, ast_pares=ast_pares,
                neg=negativos[["GRUPO", "BODEGA_NOM", "TIPO", "SERIAL", "REFERENCIA", "DESCRIPCION", "LOTE", "SISTEMA"]])


def lecturas_validas(gtin=None) -> pd.DataFrame:
    return _lecturas_validas_v(version_datos())


@st.cache_data(max_entries=3, show_spinner=False)
def _lecturas_validas_v(version: str) -> pd.DataFrame:
    L = _lecturas_por_version(version)
    if L.empty:
        return pd.DataFrame(columns=["id", "ts", "pareja", "grupo", "serial", "referencia", "lote", "cantidad",
                                     "K_REF", "K_LOTE", "SERIAL", "VENCE_L"])
    L = L[L["anulada"] == 0].copy()
    L["SERIAL"] = limpiar_codigo(L["serial"])
    L["K_REF"] = clave(limpiar_codigo(L["referencia"]))
    L["K_LOTE"] = clave(limpiar_lote(L["lote"]), es_lote=True)
    L["VENCE_L"] = parse_fecha(L["vence"])
    return L


def estado_seriales_rapido(S: pd.DataFrame) -> pd.DataFrame:
    """Estado de seriales usando una consulta agregada (no descarga todas las lecturas)."""
    if S.empty:
        return S
    R = resumen_seriales()
    if R.empty:
        Ls = pd.DataFrame(columns=["id", "SERIAL", "cantidad", "pareja", "ts"])
    else:
        R = R.copy()
        R["SERIAL"] = limpiar_codigo(R["serial"])
        filas = []
        for _, r in R.iterrows():
            filas.append(dict(SERIAL=r["SERIAL"], pareja=str(r["pareja"]), ts=str(r["ult"]),
                              cantidad=float(r["u"] or 0), n=int(r["n"] or 0)))
        Ls = pd.DataFrame(filas)
        Ls = Ls.loc[Ls.index.repeat(1)]
    E = leer_estado_seriales()
    cerr = dict(zip(E["serial"], E["estado"])) if not E.empty else {}
    quien = dict(zip(E["serial"], E["pareja"])) if not E.empty else {}
    S = S.copy()
    if not Ls.empty and "n" in Ls.columns:
        g = Ls.groupby("SERIAL").agg(LECTURAS=("n", "sum"), CONTADO=("cantidad", "sum"),
                                    PAREJAS=("pareja", lambda x: ", ".join(sorted(set(x)))), ULTIMA=("ts", "max"))
        S = S.merge(g, left_on="SERIAL", right_index=True, how="left")
    else:
        S["LECTURAS"], S["CONTADO"], S["PAREJAS"], S["ULTIMA"] = 0, 0.0, "", ""
    S[["LECTURAS", "CONTADO"]] = S[["LECTURAS", "CONTADO"]].fillna(0)
    S[["PAREJAS", "ULTIMA"]] = S[["PAREJAS", "ULTIMA"]].fillna("")
    S["ESTADO"] = np.where(S["SERIAL"].map(cerr).fillna("") == "CERRADO", "✅ CERRADO",
                           np.where(S["LECTURAS"] > 0, "🔄 EN CONTEO", "⏳ PENDIENTE"))
    S["CERRADO_POR"] = S["SERIAL"].map(quien).fillna("")
    return S


def estado_seriales(S: pd.DataFrame, L: pd.DataFrame) -> pd.DataFrame:
    E = leer_estado_seriales()
    cerr = dict(zip(E["serial"], E["estado"])) if not E.empty else {}
    quien = dict(zip(E["serial"], E["pareja"])) if not E.empty else {}
    cuando = dict(zip(E["serial"], E["ts"])) if not E.empty else {}
    if S.empty:
        return S
    S = S.copy()
    Ls = L[L["SERIAL"] != ""]
    if not Ls.empty:
        g = Ls.groupby("SERIAL").agg(LECTURAS=("id", "count"), CONTADO=("cantidad", "sum"),
                                    PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s)))), ULTIMA=("ts", "max"))
        S = S.merge(g, left_on="SERIAL", right_index=True, how="left")
    else:
        S["LECTURAS"], S["CONTADO"], S["PAREJAS"], S["ULTIMA"] = 0, 0.0, "", ""
    S[["LECTURAS", "CONTADO"]] = S[["LECTURAS", "CONTADO"]].fillna(0)
    S[["PAREJAS", "ULTIMA"]] = S[["PAREJAS", "ULTIMA"]].fillna("")
    S["ESTADO"] = np.where(S["SERIAL"].map(cerr).fillna("") == "CERRADO", "✅ CERRADO",
                           np.where(S["LECTURAS"] > 0, "🔄 EN CONTEO", "⏳ PENDIENTE"))
    S["CERRADO_POR"] = S["SERIAL"].map(quien).fillna("")
    S["CERRADO_TS"] = S["SERIAL"].map(cuando).fillna("")
    return S


def comparar(U: pd.DataFrame, L: pd.DataFrame, grupo: str, base_valor: str, Sest: pd.DataFrame | None = None):
    """Sistema (NAL) vs contado, por serial + referencia + lote, para un grupo (SMITH / SERENA)."""
    llaves = ["SERIAL", "K_REF", "K_LOTE"]
    u = U[U["GRUPO"] == grupo] if not U.empty else U
    l = L[L["grupo"] == grupo] if not L.empty else L
    col_v = "COSTO" if base_valor.startswith("Costo") else "PRECIO"
    if u.empty and l.empty:
        return pd.DataFrame()
    if not u.empty:
        Ug = u.groupby(llaves, as_index=False).agg(
            TIPO=("TIPO", "first"), SET=("SET", "first"), REF_U=("REFERENCIA", "first"), DES_U=("DESCRIPCION", "first"),
            LOTE_U=("LOTE", "first"), VENCE_U=("VENCE", "min"), SISTEMA=("SISTEMA", "sum"), COSTO_UNIT=(col_v, "max"),
            BODEGAS=("BODEGA_NOM", lambda s: ", ".join(sorted(set(map(str, s))))),
            ORIGEN=("ORIGEN_BOD", lambda s: ", ".join(sorted(set(map(str, s))))))
    else:
        Ug = pd.DataFrame(columns=llaves + ["TIPO", "SET", "REF_U", "DES_U", "LOTE_U", "VENCE_U", "SISTEMA",
                                            "COSTO_UNIT", "BODEGAS", "ORIGEN"])
    if not l.empty:
        Lg = l.groupby(llaves, as_index=False).agg(
            REF_L=("referencia", "first"), DES_L=("descripcion", "first"), LOTE_L=("lote", "first"),
            VENCE_L=("VENCE_L", "min"), CONTADO=("cantidad", "sum"), LECTURAS=("id", "count"),
            PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s)))),
            GONDOLAS=("gondola", lambda s: ", ".join(sorted({x for x in s if x}))),
            MANUAL=("modo", lambda s: int((s == "MANUAL").sum())))
    else:
        Lg = pd.DataFrame(columns=llaves + ["REF_L", "DES_L", "LOTE_L", "VENCE_L", "CONTADO", "LECTURAS",
                                            "PAREJAS", "GONDOLAS", "MANUAL"])
    M = Ug.merge(Lg, on=llaves, how="outer")
    for a, b_ in [("REF_U", "REF_L"), ("DES_U", "DES_L"), ("LOTE_U", "LOTE_L")]:
        M[a] = M[a].where(M[a].notna() & (M[a].astype(str) != ""), M[b_])
    M = M.rename(columns={"REF_U": "REFERENCIA", "DES_U": "DESCRIPCION", "LOTE_U": "LOTE"})
    M["VENCE"] = pd.to_datetime(M["VENCE_U"]).fillna(pd.to_datetime(M["VENCE_L"]))
    for c in ["SISTEMA", "CONTADO", "LECTURAS", "MANUAL"]:
        M[c] = pd.to_numeric(M[c], errors="coerce").fillna(0)
    for c in ["TIPO", "SET", "BODEGAS", "ORIGEN", "PAREJAS", "GONDOLAS", "REFERENCIA", "DESCRIPCION", "LOTE"]:
        M[c] = M[c].fillna("").astype(str)
    M["TIPO"] = np.where(M["TIPO"] == "", np.where(M["SERIAL"] != "", "SERIAL", "STOCK"), M["TIPO"])
    if not u.empty:
        cmap = u.drop_duplicates("K_REF").set_index("K_REF")[col_v]
        M["COSTO_UNIT"] = pd.to_numeric(M["COSTO_UNIT"], errors="coerce").fillna(M["K_REF"].map(cmap)).fillna(0)
    else:
        M["COSTO_UNIT"] = 0.0
    M["DIFERENCIA"] = M["CONTADO"] - M["SISTEMA"]
    est_ser = {}
    if Sest is not None and not Sest.empty:
        est_ser = dict(zip(Sest["SERIAL"], Sest["ESTADO"]))
    ser_pend = M["SERIAL"].map(est_ser).fillna("") == "⏳ PENDIENTE"
    refs_grupo = set(u["K_REF"]) if not u.empty else set()
    seriales_grupo = set(u["SERIAL"]) if not u.empty else set()
    cond = [
        (M["SISTEMA"] == 0) & (M["SERIAL"] != "") & ~M["SERIAL"].isin(seriales_grupo),
        (M["SISTEMA"] == 0) & M["K_REF"].isin(refs_grupo),
        (M["SISTEMA"] == 0),
        M["DIFERENCIA"] == 0,
        (M["CONTADO"] == 0) & ser_pend,
        (M["CONTADO"] == 0),
        M["DIFERENCIA"] < 0,
    ]
    elec = ["🆕 SERIAL NO LISTADO", "⚠️ LOTE / UBICACIÓN NO COINCIDE", "🆕 REFERENCIA NO LISTADA", "✅ CUADRADO",
            "⏳ SERIAL PENDIENTE", "🔻 FALTANTE (NO ENCONTRADO)", "🔻 FALTANTE"]
    if not conteo_cerrado():
        elec[5] = "⏳ POR CONTAR"
    M["ESTADO"] = np.select(cond, elec, "🔺 SOBRANTE")
    M["VALOR_SISTEMA"] = M["SISTEMA"] * M["COSTO_UNIT"]
    M["VALOR_DIF"] = M["DIFERENCIA"] * M["COSTO_UNIT"]
    M["DIAS_VENCE"], M["ESTADO_VENC"] = estado_venc(M["VENCE"], int(cfg("dias", "90")))
    M["DIAS_VENCE"] = M["DIAS_VENCE"].astype("Int64")
    cols = ["TIPO", "SERIAL", "SET", "REFERENCIA", "DESCRIPCION", "LOTE", "VENCE", "DIAS_VENCE", "ESTADO_VENC",
            "SISTEMA", "CONTADO", "DIFERENCIA", "ESTADO", "COSTO_UNIT", "VALOR_SISTEMA", "VALOR_DIF", "LECTURAS",
            "MANUAL", "PAREJAS", "GONDOLAS", "BODEGAS", "ORIGEN", "K_REF", "K_LOTE"]
    return M[cols].sort_values(["TIPO", "SERIAL", "REFERENCIA", "LOTE"]).reset_index(drop=True)


def totales_ref(M: pd.DataFrame) -> pd.DataFrame:
    if M.empty:
        return M
    g = M.groupby("K_REF", as_index=False).agg(
        REFERENCIA=("REFERENCIA", "first"), DESCRIPCION=("DESCRIPCION", "first"), SISTEMA=("SISTEMA", "sum"),
        CONTADO=("CONTADO", "sum"), COSTO_UNIT=("COSTO_UNIT", "max"), LOTES=("K_LOTE", "nunique"),
        SERIALES=("SERIAL", lambda s: int((s != "").sum())))
    g["DIFERENCIA"] = g["CONTADO"] - g["SISTEMA"]
    g["VALOR_DIF"] = g["DIFERENCIA"] * g["COSTO_UNIT"]
    g["ESTADO"] = np.select([g["DIFERENCIA"] == 0, g["DIFERENCIA"] < 0], ["✅ CUADRADO", "🔻 FALTANTE"], "🔺 SOBRANTE")
    return g[["REFERENCIA", "DESCRIPCION", "LOTES", "SERIALES", "SISTEMA", "CONTADO", "DIFERENCIA", "ESTADO",
              "COSTO_UNIT", "VALOR_DIF"]].sort_values("REFERENCIA")


def templete_vs_conteo(T: pd.DataFrame, L: pd.DataFrame, U: pd.DataFrame, base_valor, lotes_smith) -> pd.DataFrame:
    if T is None or T.empty:
        return pd.DataFrame()
    llaves = ["K_REF", "K_LOTE"]
    Tg = T.groupby(llaves, as_index=False).agg(REFERENCIA=("REFERENCIA", "first"), DESCRIPCION=("DESCRIPCION", "first"),
                                               LOTE=("LOTE", "first"), VENCE=("VENCE", "min"), TEMPLETE=("CANTIDAD", "sum"))
    l = L[L["grupo"] == "SMITH"] if not L.empty else L
    Lg = l.groupby(llaves, as_index=False).agg(CONTADO=("cantidad", "sum"), REF_L=("referencia", "first"),
                                               LOTE_L=("lote", "first")) if not l.empty else pd.DataFrame(columns=llaves + ["CONTADO", "REF_L", "LOTE_L"])
    u = U[U["GRUPO"] == "SMITH"] if not U.empty else U
    Ng = u.groupby(llaves, as_index=False).agg(NAL=("SISTEMA", "sum")) if not u.empty else pd.DataFrame(columns=llaves + ["NAL"])
    M = Tg.merge(Lg, on=llaves, how="outer").merge(Ng, on=llaves, how="left")
    M["REFERENCIA"] = M["REFERENCIA"].fillna(M["REF_L"]).fillna("")
    M["LOTE"] = M["LOTE"].fillna(M["LOTE_L"]).fillna("")
    M["DESCRIPCION"] = M["DESCRIPCION"].fillna("")
    for c in ["TEMPLETE", "CONTADO", "NAL"]:
        M[c] = pd.to_numeric(M[c], errors="coerce").fillna(0)
    M["DIFERENCIA"] = M["CONTADO"] - M["TEMPLETE"]
    M["ESTADO"] = np.select([M["TEMPLETE"] == 0, M["DIFERENCIA"] == 0, M["DIFERENCIA"] < 0],
                            ["⚠️ NO ESTÁ EN TEMPLETE", "✅ CUADRADO", "🔻 FALTANTE"], "🔺 SOBRANTE")
    if lotes_smith is not None and not lotes_smith.empty:
        par = set(zip(lotes_smith["K_REF"], lotes_smith["K_LOTE"]))
        M["LOTE_EN_MAESTRO_SMITH"] = ["Sí" if (a, b) in par else "No" for a, b in zip(M["K_REF"], M["K_LOTE"])]
    else:
        M["LOTE_EN_MAESTRO_SMITH"] = "N/D"
    M["DIAS_VENCE"], M["ESTADO_VENC"] = estado_venc(pd.to_datetime(M["VENCE"]), int(cfg("dias", "90")))
    M["DIAS_VENCE"] = M["DIAS_VENCE"].astype("Int64")
    return M[["REFERENCIA", "DESCRIPCION", "LOTE", "VENCE", "DIAS_VENCE", "ESTADO_VENC", "TEMPLETE", "NAL", "CONTADO",
              "DIFERENCIA", "ESTADO", "LOTE_EN_MAESTRO_SMITH"]].sort_values(["REFERENCIA", "LOTE"])



def comparar_smith_templete(ctx, L: pd.DataFrame, Se: pd.DataFrame) -> pd.DataFrame:
    """SMITH: esperado = 'Physical inventory' del templete (implantes) vs todo lo contado en Smith,
    por referencia + lote. El NAL solo aporta los seriales donde está cada lote (informativo)."""
    p, U = ctx["p"], ctx["U"]
    T = templete_df(ctx["sha_tpl"], p["hoja_tpl"])
    if T is None or T.empty:
        return pd.DataFrame()
    if p["solo_implantes"]:
        T = T[T["CLASE"] == "IMPLANTE"]
    llaves = ["K_REF", "K_LOTE"]
    Tg = T.groupby(llaves, as_index=False).agg(REF_T=("REFERENCIA", "first"), DES_T=("DESCRIPCION", "first"),
                                               LOTE_T=("LOTE", "first"), VENCE_T=("VENCE", "min"),
                                               SISTEMA=("CANTIDAD", "sum"), UBIC=("UBICACION", "first"))
    l = L[L["grupo"] == "SMITH"] if not L.empty else L
    if not l.empty:
        Lg = l.groupby(llaves, as_index=False).agg(
            REF_L=("referencia", "first"), DES_L=("descripcion", "first"), LOTE_L=("lote", "first"),
            VENCE_L=("VENCE_L", "min"), CONTADO=("cantidad", "sum"), LECTURAS=("id", "count"),
            PAREJAS=("pareja", lambda x: ", ".join(sorted(set(x)))),
            GONDOLAS=("gondola", lambda x: ", ".join(sorted({v for v in x if v}))),
            SER_L=("serial", lambda x: ", ".join(sorted({v for v in x if v}))),
            MANUAL=("modo", lambda x: int((x == "MANUAL").sum())))
    else:
        Lg = pd.DataFrame(columns=llaves + ["REF_L", "DES_L", "LOTE_L", "VENCE_L", "CONTADO", "LECTURAS", "PAREJAS",
                                            "GONDOLAS", "SER_L", "MANUAL"])
    u = U[U["GRUPO"] == "SMITH"] if not U.empty else U
    if not u.empty:
        Ng = u.groupby(llaves, as_index=False).agg(
            NAL=("SISTEMA", "sum"), DES_N=("DESCRIPCION", "first"), REF_N=("REFERENCIA", "first"),
            SER_N=("SERIAL", lambda x: ", ".join(sorted({v for v in x if v})[:6])),
            SER_LIST=("SERIAL", lambda x: tuple(sorted({v for v in x if v}))),
            STOCK_N=("TIPO", lambda x: int((x == "STOCK").sum())),
            BODEGAS=("BODEGA_NOM", lambda x: ", ".join(sorted(set(map(str, x))))))
    else:
        Ng = pd.DataFrame(columns=llaves + ["NAL", "DES_N", "REF_N", "SER_N", "SER_LIST", "STOCK_N", "BODEGAS"])
    M = Tg.merge(Lg, on=llaves, how="outer").merge(Ng, on=llaves, how="left")
    # Líneas del templete con Physical inventory = 0 (o negativo) no se esperan: solo aparecen si alguien las cuenta
    _sis = pd.to_numeric(M["SISTEMA"], errors="coerce").fillna(0)
    _con = pd.to_numeric(M["CONTADO"], errors="coerce").fillna(0)
    M = M[(_sis > 0) | (_con > 0)].copy()
    M["SISTEMA"] = _sis.clip(lower=0)
    def col(a, *otros):
        r = M[a].astype(object)
        for o in otros:
            r = r.where(r.notna() & (r.astype(str) != "") & (r.astype(str) != "nan"), M[o])
        return r.fillna("").astype(str)
    M["REFERENCIA"] = col("REF_T", "REF_L", "REF_N")
    M["DESCRIPCION"] = col("DES_T", "DES_N", "DES_L")
    M["LOTE"] = col("LOTE_T", "LOTE_L")
    M["VENCE"] = pd.to_datetime(M["VENCE_T"]).fillna(pd.to_datetime(M["VENCE_L"]))
    for c in ["SISTEMA", "CONTADO", "LECTURAS", "MANUAL", "NAL", "STOCK_N"]:
        M[c] = pd.to_numeric(M[c], errors="coerce").fillna(0)
    for c in ["PAREJAS", "GONDOLAS", "SER_N", "SER_L", "BODEGAS", "UBIC"]:
        M[c] = M[c].fillna("").astype(str)
    M["SERIAL"] = np.where(M["SER_N"] != "", M["SER_N"], M["SER_L"])
    M["SET"] = ""
    M["TIPO"] = np.where(M["SER_N"] != "", "SERIAL", "STOCK")
    M["ORIGEN"] = "Templete Smith"
    v = valref_df(ctx["sha_val"])
    col_v = "COSTO" if p["base_valor"].startswith("Costo") else "PRECIO"
    M["COSTO_UNIT"] = M["K_REF"].map(v.drop_duplicates("K_REF").set_index("K_REF")[col_v]).fillna(0) if v is not None else 0.0
    M["DIFERENCIA"] = M["CONTADO"] - M["SISTEMA"]
    # ¿El lote solo está en seriales que nadie ha empezado a contar?
    pend = set(Se.loc[Se["ESTADO"] == "⏳ PENDIENTE", "SERIAL"]) if Se is not None and not Se.empty else set()
    solo_pend = M["SER_LIST"].map(lambda t: bool(t) and isinstance(t, tuple) and all(x in pend for x in t))
    solo_pend = solo_pend & (M["STOCK_N"] == 0)
    refs_tpl = set(T["K_REF"])
    cond = [
        (M["SISTEMA"] == 0) & M["K_REF"].isin(refs_tpl),
        (M["SISTEMA"] == 0),
        M["DIFERENCIA"] == 0,
        (M["CONTADO"] == 0) & solo_pend,
        (M["CONTADO"] == 0),
        M["DIFERENCIA"] < 0,
    ]
    M["ESTADO"] = np.select(cond, ["⚠️ LOTE / UBICACIÓN NO COINCIDE", "🆕 REFERENCIA NO LISTADA", "✅ CUADRADO",
                                   "⏳ SERIAL PENDIENTE",
                                   "🔻 FALTANTE (NO ENCONTRADO)" if conteo_cerrado() else "⏳ POR CONTAR",
                                   "🔻 FALTANTE"], "🔺 SOBRANTE")
    M["VALOR_SISTEMA"] = M["SISTEMA"] * M["COSTO_UNIT"]
    M["VALOR_DIF"] = M["DIFERENCIA"] * M["COSTO_UNIT"]
    M["DIAS_VENCE"], M["ESTADO_VENC"] = estado_venc(M["VENCE"], p["dias"])
    M["DIAS_VENCE"] = M["DIAS_VENCE"].astype("Int64")
    cols = ["TIPO", "SERIAL", "SET", "REFERENCIA", "DESCRIPCION", "LOTE", "VENCE", "DIAS_VENCE", "ESTADO_VENC",
            "SISTEMA", "CONTADO", "DIFERENCIA", "ESTADO", "COSTO_UNIT", "VALOR_SISTEMA", "VALOR_DIF", "LECTURAS",
            "MANUAL", "PAREJAS", "GONDOLAS", "BODEGAS", "ORIGEN", "NAL", "K_REF", "K_LOTE"]
    return M[cols].sort_values(["REFERENCIA", "LOTE"]).reset_index(drop=True)


def marcado_asterisco(T: pd.DataFrame, ctx) -> pd.Series:
    """Líneas del templete cuya referencia o lote está marcado con * / ** (NAL, Valref o el mismo templete)."""
    UV = ctx["UV"]
    refs, pares = UV.get("ast_refs", set()), UV.get("ast_pares", set())
    m = T["K_REF"].isin(refs) | pd.Series([(a, b) in pares for a, b in zip(T["K_REF"], T["K_LOTE"])], index=T.index)
    return m | tiene_asterisco(T["LOTE"]) | tiene_asterisco(T["REFERENCIA"])


def templete_excluido_ast(ctx) -> pd.DataFrame:
    T = templete_df(ctx["sha_tpl"], ctx["p"]["hoja_tpl"]) if ctx["sha_tpl"] else None
    if T is None or T.empty:
        return pd.DataFrame()
    if ctx["p"]["solo_implantes"]:
        T = T[T["CLASE"] == "IMPLANTE"]
    X = T[marcado_asterisco(T, ctx)]
    return pd.DataFrame({"GRUPO": "SMITH", "MOTIVO": "Referencia / lote marcado con * / ** (no se cuenta)",
                         "ORIGEN_BOD": "Templete Smith", "BODEGA_NOM": X["UBICACION"], "TIPO_NAL": "",
                         "SERIAL": "", "SET": "", "REFERENCIA": X["REFERENCIA"], "DESCRIPCION": X["DESCRIPCION"],
                         "LOTE": X["LOTE"], "CANTIDAD": X["CANTIDAD"]})


def comparar_grupo(ctx, L, grupo, Se) -> pd.DataFrame:
    """Smith se compara contra 'Physical inventory' del templete; Serena contra el NAL (bodegas 66 y 67)."""
    if grupo == "SMITH" and ctx["sha_tpl"]:
        M = comparar_smith_templete(ctx, L, Se)
        if not M.empty:
            return M
    return comparar(ctx["U"], L, grupo, ctx["p"]["base_valor"], Se)


def etq_esperado(ctx, grupo) -> str:
    return "TEMPLETE (PHYSICAL INV.)" if grupo == "SMITH" and ctx["sha_tpl"] else "SISTEMA (NAL)"

def resolver_codigo(codigo: str, gtin_map: dict):
    """(referencia, lote, vencimiento, ean) a partir de lo leído por la pistola o digitado."""
    codigo = str(codigo or "").strip()
    if not codigo:
        return "", "", pd.NaT, ""
    gs = parse_gs1(codigo)
    if gs.get("01"):
        ean = gs["01"]
        return gtin_map.get(ean.lstrip("0"), ""), gs.get("10", ""), gs1_fecha(gs["17"]) if "17" in gs else pd.NaT, ean
    solo = re.sub(r"\D", "", codigo)
    if len(codigo) in (12, 13, 14) and solo == codigo:
        return gtin_map.get(codigo.lstrip("0"), ""), "", pd.NaT, codigo
    return limpiar_codigo(pd.Series([codigo])).iloc[0], "", pd.NaT, ""

# =============================================================================
# LECTOR GS1 (misma lógica de limpieza de lotes del archivo SMITH-TPN_v3.xlsm:
# módulos modParseGS1, modBatch y modMaestro)
# =============================================================================
GS = "\x1d"
GS1_FIJOS = {"01": 14, "02": 14, "11": 6, "12": 6, "13": 6, "15": 6, "16": 6, "17": 6}
GS1_VARIABLES = {"10", "21", "30", "37"}
GS1_MAX_VARIABLE = 20
GS1_MAX_CANDIDATOS = 20000


def gs1_limpiar_control(s: str) -> str:
    return s.replace(GS, "").replace("\r", "").replace("\n", "").replace("\t", "").strip()


def gs1_solo_digitos(s: str) -> str:
    return re.sub(r"\D", "", str(s or ""))


def gs1_quitar_prefijo(s: str) -> str:
    """Quita el identificador de simbología que agregan algunos lectores (]C1, ]d2, ]Q3...)."""
    c = str(s or "").strip()
    if c.startswith("]") and len(c) > 3:
        c = c[3:]
    return c


def gs1_normalizar_gtin(s: str) -> str:
    r = gs1_solo_digitos(s)
    while len(r) > 1 and r[0] == "0":
        r = r[1:]
    return r


def gs1_extraer_ean(lectura: str):
    """FASE 1 (determinista): EAN/GTIN del AI 01. Devuelve (ean, posición siguiente, se_encontró_AI01)."""
    c = gs1_quitar_prefijo(lectura)
    if len(c) >= 16 and c[:2] in ("01", "02"):
        valor = c[2:16]
        if len(valor) == 14 and valor.isdigit():
            pos = 16
            if pos < len(c) and c[pos] == GS:
                pos += 1
            return valor, pos, True
    limpio = gs1_solo_digitos(c)
    if len(limpio) >= 14:
        return limpio[:14], 0, False
    if len(limpio) >= 13:
        return limpio[:13], 0, False
    return limpio, 0, False


def gs1_formatear_fecha(seis: str):
    """AI 17: primero AAMMDD estándar (DD=00 → último día del mes); si no es válido, AAAA+MM (Mondomed)."""
    d = gs1_solo_digitos(seis)
    if len(d) != 6:
        return pd.NaT
    aa, mm, dd = int(d[:2]), int(d[2:4]), int(d[4:6])
    if 1 <= mm <= 12:
        try:
            if dd == 0:
                return (pd.Timestamp(year=2000 + aa, month=mm, day=1) + pd.offsets.MonthEnd(0)).normalize()
            return pd.Timestamp(year=2000 + aa, month=mm, day=dd)
        except Exception:
            pass
    aaaa, mm2 = int(d[:4]), int(d[4:6])
    if 1 <= mm2 <= 12 and 1950 <= aaaa <= 2200:
        try:
            return (pd.Timestamp(year=aaaa, month=mm2, day=1) + pd.offsets.MonthEnd(0)).normalize()
        except Exception:
            pass
    return pd.NaT


def _gs1_enumerar(c: str, ptr: int, lote: str, venc, venc_ok: bool, campos: int, out: list):
    """Enumera TODAS las formas de descomponer la cadena en AIs conocidos, sin asumir un orden fijo."""
    if len(out) >= GS1_MAX_CANDIDATOS:
        return
    n = len(c)
    if ptr >= n:
        out.append((lote, venc, venc_ok, campos))
        return
    if ptr == n - 1:
        if c[ptr] == GS:
            out.append((lote, venc, venc_ok, campos))
        return
    ai = c[ptr:ptr + 2]
    if not ai.isdigit():
        return
    lf = GS1_FIJOS.get(ai, 0)
    if lf:
        valor = c[ptr + 2:ptr + 2 + lf]
        if len(valor) < lf or not valor.isdigit():
            return
        nv, nok = venc, venc_ok
        if ai == "17" and pd.isna(venc):
            nv = gs1_formatear_fecha(valor)
            nok = not pd.isna(nv)
        sig = ptr + 2 + lf
        if sig < n and c[sig] == GS:
            sig += 1
        _gs1_enumerar(c, sig, lote, nv, nok, campos + 1, out)
    elif ai in GS1_VARIABLES:
        ini = ptr + 2
        maxlen = min(GS1_MAX_VARIABLE, n - ini)
        for L in range(1, maxlen + 1):
            valor = gs1_limpiar_control(c[ini:ini + L])
            if valor.strip():
                np_ = ini + L
                if np_ < n and c[np_] == GS:
                    np_ += 1
                nl = valor if (ai == "10" and not lote) else lote
                _gs1_enumerar(c, np_, nl, venc, venc_ok, campos + 1, out)


def gs1_parsear_lote_venc(lectura: str, referencia: str, pares_batch: set) -> dict:
    """FASE 2: con la referencia conocida, elige el lote validándolo contra BATCH-MAESTRO.
    Prioridad: 1) lote real registrado (el más largo) · 2) interpretación más simple con vencimiento válido
    · 3) el lote más largo."""
    res = dict(lote="", vence=pd.NaT, venc_ok=False, lote_validado=False, ai01=False)
    c = gs1_quitar_prefijo(lectura)
    _, pos, ai01 = gs1_extraer_ean(lectura)
    res["ai01"] = ai01
    if not ai01:
        return res
    cands: list = []
    _gs1_enumerar(c, pos, "", pd.NaT, False, 0, cands)
    if not cands:
        return res
    kref = clave(pd.Series([limpiar_codigo(pd.Series([referencia])).iloc[0]])).iloc[0]
    elegido, mejor_largo = None, -1
    for cand in cands:
        lt = cand[0]
        if lt:
            kl = clave(pd.Series([limpiar_lote(pd.Series([lt])).iloc[0]]), es_lote=True).iloc[0]
            if (kref, kl) in pares_batch and len(lt) > mejor_largo:
                elegido, mejor_largo = cand, len(lt)
    if elegido is not None:
        res["lote_validado"] = True
    else:
        mejor = -1
        for cand in cands:
            if cand[2]:
                score = (1000 - cand[3]) * 100 + len(cand[0])
                if score > mejor:
                    mejor, elegido = score, cand
    if elegido is None:
        elegido = max(cands, key=lambda x: len(x[0]))
    res.update(lote=elegido[0], vence=elegido[1], venc_ok=bool(elegido[2]))
    return res


@st.cache_data(max_entries=3, show_spinner=False)
def pares_batch_maestro(sha_tpn: str) -> set:
    """(referencia, lote) reales registrados en la hoja BATCH-MAESTRO del archivo TPN."""
    if not sha_tpn:
        return set()
    _, lotes = leer_maestros_tpn(bytes_maestro("tpn", sha_tpn))
    if lotes is None or lotes.empty:
        return set()
    return set(zip(lotes["K_REF"], lotes["K_LOTE"]))


def resolver_lectura(codigo: str, ctx) -> dict:
    """Interpreta una lectura de pistola como lo hace la macro del archivo de pistoleo."""
    out = dict(ref="", lote="", vence=pd.NaT, ean="", lote_validado=False, venc_ok=False, error="", cruda=str(codigo or ""))
    lectura = str(codigo or "").strip()
    if not lectura or lectura.upper() == "OK":
        out["error"] = "vacio"
        return out
    gtin = ctx["gtin"]
    ean, _, ai01 = gs1_extraer_ean(lectura)
    pares = ctx.get("pares_batch", set())
    if ai01:
        out["ean"] = ean
        out["ref"] = gtin.get(gs1_normalizar_gtin(ean), "")
        if not out["ref"]:
            out["error"] = f"EAN/GTIN no encontrado en MAESTRO: {ean}"
            return out
        r = gs1_parsear_lote_venc(lectura, out["ref"], pares)
        out.update(lote=r["lote"], vence=r["vence"], lote_validado=r["lote_validado"], venc_ok=r["venc_ok"])
        return out
    solo = gs1_solo_digitos(gs1_quitar_prefijo(lectura))
    if len(solo) >= 12 and solo == gs1_quitar_prefijo(lectura):
        out["ean"] = ean
        out["ref"] = gtin.get(gs1_normalizar_gtin(ean), "")
        if not out["ref"]:
            out["error"] = f"EAN/GTIN no encontrado en MAESTRO: {ean}"
        return out
    # Texto que no es GS1 ni EAN: se toma como referencia digitada / leída de la etiqueta
    out["ref"] = limpiar_codigo(pd.Series([gs1_quitar_prefijo(lectura)])).iloc[0]
    return out


def lote_es_valido(ref: str, lote: str, ctx) -> bool:
    pares = ctx.get("pares_batch", set())
    if not pares or not ref or not lote:
        return False
    kr = clave(limpiar_codigo(pd.Series([ref]))).iloc[0]
    kl = clave(limpiar_lote(pd.Series([lote])), es_lote=True).iloc[0]
    return (kr, kl) in pares



# =============================================================================
# CONTEXTO COMPARTIDO
# =============================================================================

def contexto():
    p = parametros()
    sha_nal, sha_val, sha_tpl, sha_tpn = sha_de("nal"), sha_de("valref"), sha_de("templete"), sha_de("tpn")
    sha_ser = sha_de("serena")
    UV = construir_universo(sha_nal, sha_val, p["criterio"], p["incluir_otras"], p["dias"], sha_tpl, p["hoja_tpl"],
                            sha_ser, p["hoja_ser"], p["solo_implantes"])
    gtin, lotes = maestros_smith(sha_tpn, sha_val)
    pares = pares_batch_maestro(sha_tpn)
    return dict(p=p, UV=UV, pares_batch=pares, U=UV["U"], S=UV["S"], gtin=gtin, lotes=lotes, sha_tpl=sha_tpl, sha_val=sha_val,
                sha_ser=sha_ser, implantes=UV.get("implantes", set()), instrumental=UV.get("instrumental", set()))


def enfocar(etiqueta: str):
    """Deja el cursor en el campo del código para que la pistola escriba allí sin hacer clic."""
    html = (
        "<script>const f=()=>{const el=window.parent.document.querySelector('input[aria-label=\"" + etiqueta +
        "\"]');if(el){el.focus();return true}return false};let n=0;const t=setInterval(()=>{if(f()||++n>20)clearInterval(t)},150);</script>")
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=0)

# =============================================================================
# CORRECCIÓN Y ELIMINACIÓN DE LECTURAS (con historial de auditoría)
# =============================================================================
EDITABLES = ["serial", "referencia", "lote", "vence", "cantidad", "gondola", "nivel", "observacion"]


@st.cache_data(ttl=4, show_spinner=False)
def leer_correcciones() -> pd.DataFrame:
    return consultar(select(T_COR)).fillna("")


def marcar_posibles_dobles(df: pd.DataFrame, segundos: int = 5) -> pd.Series:
    """Misma pareja, referencia, lote y serial leídos con pocos segundos de diferencia: posible doble disparo."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df.copy()
    d["_t"] = pd.to_datetime(d["ts"], errors="coerce")
    d = d.sort_values("_t")
    llave = ["pareja", "referencia", "lote", "serial"]
    dif = d.groupby(llave)["_t"].diff().dt.total_seconds()
    sig = d.groupby(llave)["_t"].diff(-1).dt.total_seconds().abs()
    marca = (dif <= segundos) | (sig <= segundos)
    return marca.reindex(df.index).fillna(False)


def _limpia_valor(campo: str, v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        v = ""
    if campo == "referencia":
        return limpiar_codigo(pd.Series([v])).iloc[0]
    if campo == "lote":
        return limpiar_lote(pd.Series([v])).iloc[0]
    if campo == "serial":
        return limpiar_codigo(pd.Series([v])).iloc[0]
    if campo == "cantidad":
        try:
            return float(v)
        except Exception:
            return None
    if campo == "vence":
        if isinstance(v, (datetime, date, pd.Timestamp)):
            return pd.Timestamp(v).strftime("%Y-%m-%d")
        f = parse_fecha(pd.Series([v])).iloc[0]
        return "" if pd.isna(f) else f.strftime("%Y-%m-%d")
    return str(v).strip()


def guardar_correcciones(original: pd.DataFrame, editado: pd.DataFrame, usuario: str, ctx, es_admin: bool):
    """Compara la tabla original con la editada, valida y guarda cambios + anulaciones + historial."""
    ahora_s = ahora().strftime("%Y-%m-%d %H:%M:%S")
    cambios, errores, hist = 0, [], []
    U = ctx["U"]
    with bd().begin() as c:
        for lid, r in editado.iterrows():
            o = original.loc[lid]
            # Eliminar (anular) / restaurar
            if bool(r.get("ELIMINAR", False)) and int(o.get("anulada", 0)) == 0:
                c.execute(update(T_LECT).where(T_LECT.c.id == lid).values(anulada=1, anulada_por=usuario, anulada_ts=ahora_s))
                hist.append(dict(lectura_id=lid, campo="ELIMINADA", antes="activa", despues="anulada"))
                cambios += 1
                continue
            if es_admin and bool(r.get("RESTAURAR", False)) and int(o.get("anulada", 0)) == 1:
                c.execute(update(T_LECT).where(T_LECT.c.id == lid).values(anulada=0, anulada_por="", anulada_ts=""))
                hist.append(dict(lectura_id=lid, campo="RESTAURADA", antes="anulada", despues="activa"))
                cambios += 1
                continue
            vals = {}
            for campo in EDITABLES:
                if campo not in editado.columns:
                    continue
                nuevo, viejo = _limpia_valor(campo, r[campo]), _limpia_valor(campo, o[campo])
                if nuevo != viejo:
                    vals[campo] = nuevo
            if not vals:
                continue
            ref_final = vals.get("referencia", o["referencia"])
            grupo = o.get("grupo", "")
            if "cantidad" in vals and (vals["cantidad"] is None or vals["cantidad"] <= 0):
                errores.append(f"{o['referencia']}: la cantidad debe ser mayor que 0 (para quitar la lectura use ELIMINAR).")
                continue
            if "referencia" in vals and not ref_final:
                errores.append("La referencia no puede quedar vacía.")
                continue
            if "referencia" in vals and es_instrumental(ref_final, grupo, ctx) and not es_admin:
                errores.append(f"{ref_final} es INSTRUMENTAL: no se cuenta.")
                continue
            if "referencia" in vals and not U.empty:
                m = U[U["K_REF"] == clave(pd.Series([ref_final])).iloc[0]]
                vals["descripcion"] = m["DESCRIPCION"].iloc[0] if len(m) else ""
            # Re-validar el lote contra BATCH-MAESTRO y actualizar la marca 🟡
            if ("referencia" in vals or "lote" in vals) and "observacion" not in vals:
                lote_final = vals.get("lote", o["lote"])
                obs = re.sub(r"^⚠ REVISAR:[^·]*(· VENCIMIENTO NO LEÍDO)?\s*·?\s*", "", str(o.get("observacion", ""))).strip()
                if ctx.get("pares_batch") and lote_final and not lote_es_valido(ref_final, lote_final, ctx):
                    obs = ("⚠ REVISAR: LOTE SIN VALIDAR EN BATCH-MAESTRO · " + obs).strip(" ·")
                if obs != str(o.get("observacion", "")):
                    vals["observacion"] = obs
            c.execute(update(T_LECT).where(T_LECT.c.id == lid).values(**vals))
            for campo, nuevo in vals.items():
                if campo == "descripcion":
                    continue
                hist.append(dict(lectura_id=lid, campo=campo.upper(), antes=str(o.get(campo, ""))[:300], despues=str(nuevo)[:300]))
            cambios += 1
        for h in hist:
            c.execute(insert(T_COR).values(id=uuid.uuid4().hex[:16], ts=ahora_s, usuario=usuario, **h))
    leer_lecturas.clear()
    leer_correcciones.clear()
    return cambios, errores


def rerun_fragmento():
    """Vuelve a dibujar solo el bloque de pistoleo (rápido); si no aplica, la página completa."""
    try:
        st.rerun(scope="fragment")
    except Exception:
        st.rerun()


def editor_lecturas(L: pd.DataFrame, usuario: str, ctx, es_admin: bool, clave_ed: str, alto: int = 360,
                    en_fragmento: bool = False):
    """Tabla editable: corregir campos, eliminar pistoleos dobles y (admin) restaurar eliminadas."""
    if L.empty:
        st.info("No hay lecturas para mostrar.")
        return
    v = L.copy()
    v["POSIBLE DOBLE"] = np.where(marcar_posibles_dobles(v), "🔁 sí", "")
    v["vence"] = pd.to_datetime(v["vence"], errors="coerce")
    v["cantidad"] = pd.to_numeric(v["cantidad"], errors="coerce").fillna(0)
    cols = ["ts", "POSIBLE DOBLE", "pareja", "modo", "zona", "serial", "referencia", "descripcion", "lote", "vence",
            "cantidad", "gondola", "nivel", "observacion", "anulada"]
    v = v.set_index("id")[[c for c in cols if c in v.columns]]
    v.insert(0, "ELIMINAR", False)
    if es_admin:
        v.insert(1, "RESTAURAR", False)
    editables = ["ELIMINAR", "RESTAURAR"] + EDITABLES
    if not es_admin:
        editables = [e for e in editables if e != "observacion"]
    ver = st.session_state.setdefault("ver_corr", 0)
    ed = st.data_editor(
        v, hide_index=True, height=alto, key=f"{clave_ed}_{ver}_{len(v)}", num_rows="fixed",
        disabled=[c for c in v.columns if c not in editables],
        column_config={
            "ELIMINAR": st.column_config.CheckboxColumn("🗑️ ELIMINAR", help="Marque para eliminar (ej. pistoleo doble)"),
            "RESTAURAR": st.column_config.CheckboxColumn("↩️ RESTAURAR", help="Volver a activar una lectura eliminada"),
            "ts": st.column_config.TextColumn("FECHA / HORA"),
            "serial": st.column_config.TextColumn("SERIAL ✏️"),
            "referencia": st.column_config.TextColumn("REFERENCIA ✏️"),
            "lote": st.column_config.TextColumn("LOTE ✏️"),
            "vence": st.column_config.DateColumn("VENCE ✏️", format="DD/MM/YYYY"),
            "cantidad": st.column_config.NumberColumn("CANT. ✏️", min_value=0, step=1, format="%d"),
            "gondola": st.column_config.TextColumn("GÓNDOLA ✏️"),
            "nivel": st.column_config.TextColumn("NIVEL ✏️"),
            "observacion": st.column_config.TextColumn("OBSERVACIÓN" + (" ✏️" if es_admin else "")),
            "anulada": st.column_config.CheckboxColumn("ELIMINADA"),
        })
    n_del = int(ed["ELIMINAR"].sum())
    n_res = int(ed["RESTAURAR"].sum()) if "RESTAURAR" in ed.columns else 0
    comparables = [c for c in EDITABLES if c in ed.columns]
    n_mod = int((ed[comparables].astype(str) != v[comparables].astype(str)).any(axis=1).sum())
    c1, c2 = st.columns([2, 3])
    etiqueta = f"💾 Guardar cambios ({n_mod} corregida(s) · {n_del} a eliminar" + (f" · {n_res} a restaurar" if es_admin else "") + ")"
    if c1.button(etiqueta, type="primary", disabled=(n_mod + n_del + n_res) == 0, key=f"guardar_{clave_ed}", width="stretch"):
        orig = L.set_index("id")
        n, errores = guardar_correcciones(orig, ed, usuario, ctx, es_admin)
        for e in errores:
            st.error(e)
        st.session_state.ver_corr = ver + 1
        st.session_state[f"msg_corr_{clave_ed}"] = f"✔ {n} lectura(s) actualizada(s). Quedó registro en el historial."
        (rerun_fragmento() if en_fragmento else st.rerun())
    if c2.button("↺ Descartar cambios sin guardar", key=f"desc_{clave_ed}"):
        st.session_state.ver_corr = ver + 1
        (rerun_fragmento() if en_fragmento else st.rerun())
    if st.session_state.get(f"msg_corr_{clave_ed}"):
        st.success(st.session_state.pop(f"msg_corr_{clave_ed}"))



def conteo_cerrado() -> bool:
    """Mientras el conteo esté abierto, lo no contado es 'Por contar'; al cerrarlo pasa a 'Faltante'."""
    return cfg("conteo_cerrado", "0") == "1"


def es_instrumental(ref: str, grupo: str, ctx) -> bool:
    """Smith: todo lo que no sea implante del templete es instrumental y no se cuenta."""
    if grupo != "SMITH" or not ctx["p"]["solo_implantes"] or not ctx["implantes"]:
        return False
    k = clave(limpiar_codigo(pd.Series([ref]))).iloc[0]
    if k in ctx["implantes"]:
        return False
    if k in ctx["instrumental"]:
        return True
    U = ctx["UV"].get("excl")
    return U is not None and not U.empty and k in set(clave(limpiar_codigo(U.loc[U["MOTIVO"].astype(str).str.startswith("Instrumental"), "REFERENCIA"])))


# =============================================================================
# PANTALLA DE CONTEO (parejas · conteo a ciegas)
# =============================================================================
ETQ_CODIGO = "Código (pistola o digitado)"


def pantalla_conteo(par: dict, ctx: dict, es_admin: bool = False):
    pid = par["nombre"]
    U, S, gtin = ctx["U"], ctx["S"], ctx["gtin"]
    st.markdown(f'<div class="pareja-head"><b>👥 {pid}</b> &nbsp; {par.get("aux1", "")} / {par.get("aux2", "")}'
                f' &nbsp;·&nbsp; 📍 {par.get("zona", "")}'
                + (f' &nbsp;·&nbsp; 🗄️ {par.get("gondolas")}' if par.get("gondolas") else "") + '</div>',
                unsafe_allow_html=True)
    if U.empty:
        alerta("⏳ El administrador aún no ha cargado el archivo NAL. Puede registrar lecturas igualmente.", "ambar")
    z1, z2 = st.columns([2, 3])
    zonas = list(ZONAS)
    zona = z1.selectbox("Zona", zonas, index=zonas.index(par["zona"]) if par.get("zona") in zonas else 0, key=f"zona_{pid}")
    grupo = ZONAS[zona]
    modo = z2.radio("¿Qué está contando?", ["📦 Stock de seguridad (sin serial)", "🧰 Serial / Kit"], horizontal=True,
                    key=f"modo_{pid}")
    es_stock = modo.startswith("📦")
    # Góndola y nivel aplican SOLO al stock de seguridad; en seriales lo obligatorio es el número de serial.
    if es_stock:
        g1, g2 = st.columns(2)
        gon = g1.text_input("Góndola / estante *", value=st.session_state.get(f"gon_mem_{pid}", ""), key=f"gon_{pid}")
        niv = g2.text_input("Nivel *", value=st.session_state.get(f"niv_mem_{pid}", ""), key=f"niv_{pid}")
        st.session_state[f"gon_mem_{pid}"], st.session_state[f"niv_mem_{pid}"] = gon, niv
        if not gon.strip() or not niv.strip():
            st.caption("📍 Para stock de seguridad diligencie **góndola/estante y nivel** antes de pistolear.")
    else:
        gon, niv = "", ""
    serial = ""
    if modo.startswith("🧰"):
        Sest = estado_seriales_rapido(S[S["GRUPO"] == grupo]) if not S.empty else pd.DataFrame()
        if zona.endswith("66") or zona.endswith("67"):
            bod = int(zona[-2:])
            if not Sest.empty:
                Sest = Sest[Sest["BODEGA"] == bod]
        s1, s2 = st.columns([3, 2])
        opciones = ["— seleccione un serial —"]
        etiquetas = {}
        if not Sest.empty:
            vista = Sest.sort_values(["ESTADO", "SERIAL"], key=lambda c: c.map({"⏳ PENDIENTE": 0, "🔄 EN CONTEO": 1, "✅ CERRADO": 2}) if c.name == "ESTADO" else c)
            for _, r in vista.iterrows():
                e = f'{r["ESTADO"]} · {r["SERIAL"]} · {r["SET"][:45]} · {r["BODEGA_NOM"][:22]}'
                opciones.append(e)
                etiquetas[e] = r["SERIAL"]
        sel = s1.selectbox("Serial pendiente (puede escribir para buscar)", opciones, key=f"selser_{pid}")
        escrito = s2.text_input("…o escanee / digite el número de serial", key=f"txtser_{pid}")
        serial = limpiar_codigo(pd.Series([escrito])).iloc[0] if escrito.strip() else etiquetas.get(sel, "")
        if not Sest.empty:
            pend = (Sest["ESTADO"] == "⏳ PENDIENTE").sum()
            enc = (Sest["ESTADO"] == "🔄 EN CONTEO").sum()
            cer = (Sest["ESTADO"] == "✅ CERRADO").sum()
            st.markdown(f'<span class="chip no">⏳ {pend} pendientes</span><span class="chip info">🔄 {enc} en conteo</span>'
                        f'<span class="chip ok">✅ {cer} cerrados</span>', unsafe_allow_html=True)
        if serial:
            fila = Sest[Sest["SERIAL"] == serial] if not Sest.empty else pd.DataFrame()
            if fila.empty:
                alerta(f"🆕 El serial <b>{serial}</b> no está en el listado de esta zona: se registrará como novedad.", "ambar")
            else:
                r = fila.iloc[0]
                alerta(f"🧰 Contando serial <b>{serial}</b> · {r['SET']} · {r['BODEGA_NOM']} · Estado: <b>{r['ESTADO']}</b>"
                       + (f" (por {r['CERRADO_POR']})" if r["ESTADO"] == "✅ CERRADO" else ""),
                       "verde" if r["ESTADO"] != "✅ CERRADO" else "azul")
                if r["ESTADO"] == "✅ CERRADO" and not es_admin:
                    st.warning("Este serial ya fue cerrado. Si necesita volver a contarlo, pida al administrador que lo reabra.")
            c1, c2 = st.columns(2)

            def _cerrar(s_=serial, g_=grupo, p_=pid):
                fijar_estado_serial(s_, g_, "CERRADO", p_)
                st.session_state[f"txtser_{p_}"] = ""
                st.session_state[f"selser_{p_}"] = "— seleccione un serial —"
                st.session_state[f"ult_{p_}"] = ("ok", f"✅ Serial {s_} cerrado.")
            c1.button("✅ Cerrar serial (terminé de contarlo)", type="primary", width="stretch", key=f"cerrar_{pid}",
                      on_click=_cerrar)
            if es_admin and c2.button("↩️ Reabrir serial", width="stretch", key=f"reabrir_{pid}"):
                fijar_estado_serial(serial, grupo, None)
                st.rerun()
        else:
            st.info("Seleccione o escanee el serial antes de pistolear su contenido.")

    if grupo == "SMITH" and ctx["p"]["solo_implantes"] and ctx["implantes"]:
        st.caption("🦴 En Smith & Nephew se cuentan **solo implantes**. El instrumental no se registra.")
    bloqueado = modo.startswith("🧰") and not serial
    bloque_registro(par, ctx, es_admin, zona, grupo, es_stock, gon, niv, serial, bloqueado)


@st.fragment
def bloque_registro(par, ctx, es_admin, zona, grupo, es_stock, gon, niv, serial, bloqueado):
    """Se actualiza SOLO este bloque al pistolear: la pantalla responde al instante."""
    pid = par["nombre"]
    U = ctx["U"]
    pend = vaciar_cola_pendiente()
    if pend:
        alerta(f"📶 Sin conexión con la base: <b>{pend}</b> lectura(s) guardadas en este equipo, se reintentan solas. "
               "No cierre esta ventana.", "roja")
        if st.button("🔄 Reintentar ahora", key=f"reint_{pid}"):
            rerun_fragmento()
    # ---- Pistolear
    with st.form(f"form_pist_{pid}", clear_on_submit=True):
        f1, f2, f3 = st.columns([3, 1.4, 0.8])
        cod = f1.text_input(ETQ_CODIGO, key=f"cod_{pid}", placeholder="Escanee aquí y la pistola dará Enter")
        lote = f2.text_input("Lote (si el código no lo trae)", key=f"lote_{pid}")
        cant = f3.number_input("Cantidad", min_value=1, value=1, step=1, key=f"cant_{pid}")
        enviar = st.form_submit_button("📥 Registrar", type="primary", width="stretch", disabled=bloqueado)
    if enviar and cod.strip():
        r = resolver_lectura(cod, ctx)
        ref = r["ref"]
        ven = r["vence"]
        lote_f = limpiar_lote(pd.Series([lote or r["lote"]])).iloc[0]
        validado = r["lote_validado"] or (bool(lote) and lote_es_valido(ref, lote_f, ctx))
        if r["error"] == "vacio":
            pass
        elif es_stock and (not gon.strip() or not niv.strip()):
            st.session_state[f"ult_{pid}"] = ("no", "📍 Stock de seguridad: diligencie <b>GÓNDOLA / ESTANTE</b> y <b>NIVEL</b> antes de escanear.")
        elif not es_stock and not serial:
            st.session_state[f"ult_{pid}"] = ("no", "🧰 Seleccione o escanee primero el <b>SERIAL</b> que está contando.")
        elif r["error"]:
            st.session_state[f"ult_{pid}"] = ("no", f"❌ {r['error']}. Verifique el código o use <b>✍️ Registro manual</b>.")
        elif not ref:
            st.session_state[f"ult_{pid}"] = ("no", f"No se reconoce el código «{cod}». Use <b>✍️ Registro manual</b> y digite la referencia.")
        elif es_instrumental(ref, grupo, ctx) and not es_admin:
            st.session_state[f"ult_{pid}"] = ("no", f"🔧 <b>{ref}</b> es INSTRUMENTAL: no se cuenta. Continúe con el siguiente implante.")
        else:
            desc = ""
            if not U.empty:
                m = U[U["K_REF"] == clave(pd.Series([ref])).iloc[0]]
                desc = m["DESCRIPCION"].iloc[0] if len(m) else ""
            revisar = []
            if ctx.get("pares_batch") and lote_f and not validado:
                revisar.append("LOTE SIN VALIDAR EN BATCH-MAESTRO")
            if r["ean"] and pd.isna(ven):
                revisar.append("VENCIMIENTO NO LEÍDO")
            fila = registrar_lectura(pareja=pid, auxiliares=f'{par.get("aux1", "")} / {par.get("aux2", "")}', modo="PISTOLA",
                              grupo=grupo, zona=zona, gondola=gon.strip(), nivel=niv.strip(), serial=serial,
                              codigo_leido=r["cruda"].strip()[:300], referencia=ref, descripcion=desc, lote=lote_f,
                              vence=ven.strftime("%Y-%m-%d") if not pd.isna(ven) else "", cantidad=cant,
                              observacion=("⚠ REVISAR: " + " · ".join(revisar)) if revisar else "",
                              origen="Admin" if es_admin else "Pareja")
            msg = (f"✔ {ref} · lote <b>{lote_f or 'SIN LOTE'}</b>"
                   + (f" · vence {ven:%d/%m/%Y}" if not pd.isna(ven) else "") + f" × {int(cant)}"
                   + (f" · serial {serial}" if serial else ""))
            if not fila.get("_guardada", True):
                msg += "<br>📶 Guardada en este equipo (sin conexión): se enviará automáticamente."
            if revisar:
                msg += "<br>🟡 Revise la etiqueta: " + " · ".join(revisar).lower()
                st.session_state[f"ult_{pid}"] = ("rev", msg)
            else:
                st.session_state[f"ult_{pid}"] = ("ok", msg)
    elif enviar:
        st.session_state[f"ult_{pid}"] = ("no", "El código está vacío.")
    if f"ult_{pid}" in st.session_state:
        t, m = st.session_state[f"ult_{pid}"]
        st.markdown(f'<div class="{ {"ok": "ok-scan", "rev": "rev-scan"}.get(t, "no-scan") }">{m}</div>', unsafe_allow_html=True)
    if not bloqueado and not es_admin:
        enfocar(ETQ_CODIGO)

    # ---- Registro manual (referencias que no se pueden pistolear)
    with st.expander("✍️ Registro manual · la etiqueta no se puede leer / referencia sin código", expanded=False):
        with st.form(f"form_man_{pid}", clear_on_submit=True):
            m1, m2, m3, m4 = st.columns([1.6, 1.4, 1.2, 0.8])
            m_ref = m1.text_input("Referencia *")
            m_lot = m2.text_input("Lote")
            m_ven = m3.date_input("Vencimiento", value=None, format="DD/MM/YYYY")
            m_can = m4.number_input("Cantidad *", min_value=1, value=1, step=1)
            m5, m6 = st.columns([2, 2])
            m_des = m5.text_input("Descripción (opcional)")
            m_obs = m6.text_input("Observación (ej. etiqueta borrosa)")
            if st.form_submit_button("💾 Guardar registro manual", type="primary", disabled=bloqueado):
                if not m_ref.strip():
                    st.error("La referencia es obligatoria.")
                elif es_stock and (not gon.strip() or not niv.strip()):
                    st.error("Stock de seguridad: diligencie góndola/estante y nivel arriba antes de guardar.")
                elif not es_stock and not serial:
                    st.error("Seleccione primero el serial que está contando.")
                elif es_instrumental(m_ref, grupo, ctx) and not es_admin:
                    st.error("Esa referencia es INSTRUMENTAL: no se cuenta.")
                else:
                    ref = limpiar_codigo(pd.Series([m_ref])).iloc[0]
                    lote_f = limpiar_lote(pd.Series([m_lot])).iloc[0]
                    desc = m_des.strip()
                    if not desc and not U.empty:
                        mm = U[U["K_REF"] == clave(pd.Series([ref])).iloc[0]]
                        desc = mm["DESCRIPCION"].iloc[0] if len(mm) else ""
                    if ctx.get("pares_batch") and lote_f and not lote_es_valido(ref, lote_f, ctx):
                        m_obs = ("⚠ REVISAR: LOTE SIN VALIDAR EN BATCH-MAESTRO · " + m_obs).strip(" ·")
                    registrar_lectura(pareja=pid, auxiliares=f'{par.get("aux1", "")} / {par.get("aux2", "")}',
                                      modo="MANUAL", grupo=grupo, zona=zona, gondola=gon.strip(), nivel=niv.strip(),
                                      serial=serial, codigo_leido="", referencia=ref, descripcion=desc, lote=lote_f,
                                      vence=m_ven.isoformat() if m_ven else "", cantidad=m_can, observacion=m_obs.strip(),
                                      origen="Admin" if es_admin else "Pareja")
                    st.session_state[f"ult_{pid}"] = ("ok", f"✍️ Manual: {ref} · lote {lote_f or 'SIN LOTE'} × {int(m_can)}")
                    rerun_fragmento()

    # ---- Mis lecturas
    Lp = lecturas_de_pareja(pid)
    Lp = Lp[Lp["anulada"] == 0] if not Lp.empty else Lp
    k = st.columns(3)
    kpi(k[0], "Mis lecturas", fmt_num(len(Lp)), "registros activos", C["teal"])
    kpi(k[1], "Mis unidades", fmt_num(Lp["cantidad"].sum() if not Lp.empty else 0), "contadas por esta pareja", C["navy"])
    E = leer_estado_seriales()
    kpi(k[2], "Seriales cerrados", fmt_num((E["pareja"] == pid).sum() if not E.empty else 0), "por esta pareja", C["verde"])
    st.markdown("#### 📝 Mis lecturas · corregir o eliminar")
    st.caption("Corrija directamente en la tabla las columnas con ✏️ (referencia, lote, vencimiento, cantidad, góndola, "
               "nivel, serial). Para un pistoleo doble marque 🗑️ ELIMINAR. Luego pulse 💾 Guardar cambios. "
               "La columna 🔁 POSIBLE DOBLE avisa lecturas iguales hechas con pocos segundos de diferencia.")
    if not Lp.empty:
        f1, f2, f3 = st.columns([2, 1.2, 1.2])
        bq = f1.text_input("🔎 Buscar referencia, lote o serial", key=f"bq_{pid}")
        solo_d = f2.toggle("🔁 Solo posibles dobles", key=f"sd_{pid}")
        solo_s = f3.toggle("Solo serial actual", key=f"ss_{pid}", disabled=not serial)
        v = Lp.sort_values("ts", ascending=False)
        if bq.strip():
            b_ = bq.strip().upper()
            v = v[v["referencia"].str.upper().str.contains(b_, regex=False) | v["lote"].str.upper().str.contains(b_, regex=False)
                  | v["serial"].str.upper().str.contains(b_, regex=False)]
        if solo_s and serial:
            v = v[v["serial"] == serial]
        if solo_d:
            v = v[marcar_posibles_dobles(v)]
        editor_lecturas(v.head(300), pid, ctx, es_admin=es_admin, clave_ed=f"mis_{pid}", alto=320, en_fragmento=True)


# =============================================================================
# ADMINISTRADOR
# =============================================================================

def admin_maestros(ctx):
    seccion("📂 Archivos maestros (se guardan en la base de datos para todos)")
    st.caption("Cargue cada archivo y pulse **Guardar**. Las parejas no necesitan cargar nada.")
    c = st.columns(3) + st.columns(3)
    specs = [("templete", "Templete / Kardex Smith & Nephew", ["xlsx", "xlsm", "xls", "csv"]),
             ("serena", "Templete Serena del Mar", ["xlsx", "xlsm", "xls", "csv"]),
             ("nal", "Archivo Nacional (NAL)", ["csv", "txt"]),
             ("valref", "Referencias Valref", ["csv", "txt", "xlsx"]),
             ("tpn", "Archivo TPN (hojas MAESTRO / BATCH-MAESTRO)", ["xlsm", "xlsx"]),
             ("gastos", "Gastos / consumos (Con_Equipo)", ["csv", "txt", "xlsx"])]
    for col, (tipo, etq, tipos) in zip(c, specs):
        with col:
            up = st.file_uploader(etq, type=tipos, key=f"up_{tipo}")
            if up is not None and st.button(f"💾 Guardar {tipo.upper()}", key=f"g_{tipo}", type="primary", width="stretch"):
                with st.spinner("Guardando…"):
                    guardar_maestro(tipo, up.name, up.getvalue())
                st.success("Guardado.")
                st.rerun()
    m = maestros_meta()
    if not m.empty:
        mm = m.copy()
        mm["tam"] = (mm["tam"] / 1_048_576).round(2).astype(str) + " MB"
        st.dataframe(mm.rename(columns={"tipo": "TIPO", "nombre": "ARCHIVO", "ts": "CARGADO", "tam": "TAMAÑO"}).drop(columns=["sha"]),
                     hide_index=True)
    for tipo_h, clave_h, etq_h in [("templete", "hoja_tpl", "Hoja del templete Smith"), ("serena", "hoja_ser", "Hoja del templete Serena")]:
        if not sha_de(tipo_h) or nombre_de(tipo_h).lower().endswith((".csv", ".txt")):
            continue
        try:
            hs = hojas_excel(bytes_maestro(tipo_h, sha_de(tipo_h)))
        except Exception:
            hs = []
        if len(hs) > 1:
            actual = ctx["p"][clave_h] or hs[0]
            h = st.selectbox(etq_h, hs, index=hs.index(actual) if actual in hs else 0, key=f"sel_{clave_h}")
            if h != ctx["p"][clave_h]:
                cfg_set(clave_h, h)
                st.rerun()
    UV = ctx["UV"]
    if UV["info"]:
        i = UV["info"]
        if not i.get("smith_tpl"):
            alerta("⚠️ Falta el <b>Templete Smith</b>: sin él no se puede separar implantes de instrumental.", "ambar")
        if not i.get("serena_tpl"):
            alerta("⚠️ Falta el <b>Templete Serena del Mar</b>: mientras tanto se cuenta todo lo de las bodegas 66 y 67.", "ambar")
        alerta(f"🎯 Alcance: Smith <b>{fmt_num(i.get('seriales_smith', 0))}</b> seriales (solo implantes del templete) · "
               f"Serena <b>{fmt_num(i.get('seriales_serena', 0))}</b> seriales · <b>{fmt_num(i.get('instrumental_lineas', 0))}</b> "
               f"líneas de instrumental fuera del conteo", "verde")
        alerta(f"🧾 Inventario a contar: <b>{fmt_num(i['lineas'])}</b> líneas · <b>{fmt_num(i['seriales'])}</b> seriales · "
               f"<b>{fmt_num(i['seriales_otras'])}</b> seriales de equipos de ciudad 02·10·20·27·33 ({fmt_num(i['otras_bodegas'])} líneas) · "
               f"<b>{fmt_num(i.get('fuera_alcance', 0))}</b> registros fuera de alcance · "
               f"<b>{fmt_num(i['descuadres_com_lot'])}</b> descuadres Com vs Lot · "
               f"<b>{fmt_num(i.get('negativos', 0))}</b> líneas con saldo negativo en el NAL (no se cuentan)", "azul")

    seccion("⚙️ Parámetros")
    p = ctx["p"]
    with st.form("form_param"):
        a, b, c3 = st.columns(3)
        cliente = a.text_input("Cliente / proveedor", p["cliente"])
        resp = b.text_input("Responsable del conteo", p["responsable"])
        dias = c3.number_input("Alerta 'próximo a vencer' (días)", 15, 365, p["dias"], step=15)
        d, e, f = st.columns(3)
        opc_c = ["Propietaria (BODEGA PROPIE.)", "Existencia (BOD-EXISTENCIA)"]
        criterio = d.radio("Filtrar bodegas del NAL por", opc_c, index=opc_c.index(p["criterio"]) if p["criterio"] in opc_c else 0)
        opc_v = ["Costo promedio (Valref)", "Precio de venta (Valref)"]
        base_valor = e.radio("Valorizar con", opc_v, index=opc_v.index(p["base_valor"]) if p["base_valor"] in opc_v else 0)
        incl = f.toggle("Incluir seriales de equipos de cada ciudad (bod. 02·10·20·27·33): refs del templete con lote sin * / **",
                        value=p["incluir_otras"])
        solo_imp = d.toggle("Smith: contar solo IMPLANTES del templete (el instrumental no se cuenta)",
                            value=p["solo_implantes"])
        avisos = f.toggle("Avisar a las parejas si el lote no figura en el listado", value=p["avisos_pareja"],
                          help="Apagado = conteo 100 % a ciegas.")
        if st.form_submit_button("Guardar parámetros", type="primary"):
            for k_, v_ in [("cliente", cliente), ("responsable", resp), ("dias", int(dias)), ("criterio", criterio),
                           ("base_valor", base_valor), ("incluir_otras", "1" if incl else "0"), ("avisos_pareja", "1" if avisos else "0"),
                           ("solo_implantes", "1" if solo_imp else "0")]:
                cfg_set(k_, v_)
            st.success("Parámetros guardados.")
            st.rerun()

    seccion("🏁 Cierre del conteo")
    if conteo_cerrado():
        alerta("🏁 El conteo está <b>CERRADO</b>: todo lo que no se encontró figura como <b>faltante</b>.", "roja")
        if st.button("Reabrir conteo"):
            cfg_set("conteo_cerrado", "0")
            st.rerun()
    else:
        alerta("🟢 El conteo está <b>ABIERTO</b>: lo que aún no se ha contado figura como <b>⏳ Por contar</b>, no como faltante.", "verde")
        ok = st.checkbox("Confirmo que terminó el conteo físico")
        if st.button("🏁 Cerrar conteo (lo no contado pasa a faltante)", disabled=not ok, type="primary"):
            cfg_set("conteo_cerrado", "1")
            st.rerun()

    seccion("🔑 Seguridad")
    with st.form("form_clave"):
        n1, n2 = st.columns(2)
        c1_ = n1.text_input("Nueva contraseña de administrador", type="password")
        c2_ = n2.text_input("Repita la contraseña", type="password")
        if st.form_submit_button("Cambiar contraseña"):
            if len(c1_) < 6 or c1_ != c2_:
                st.error("La contraseña debe tener al menos 6 caracteres y coincidir.")
            else:
                cambiar_clave_admin(c1_)
                st.success("Contraseña actualizada.")
    if not cfg("admin_hash"):
        alerta("⚠️ Está usando la contraseña inicial. Cámbiela antes del conteo.", "ambar")

    seccion("🧹 Reinicio del conteo")
    st.caption("Use esto solo para empezar un inventario nuevo. Descargue antes los reportes.")
    conf = st.text_input("Escriba BORRAR para habilitar")
    if st.button("Borrar TODAS las lecturas y estados de seriales", disabled=conf.strip().upper() != "BORRAR"):
        ejecutar(delete(T_LECT))
        ejecutar(delete(T_SER))
        limpiar_caches_conteo()
        st.success("Conteo reiniciado.")
        st.rerun()


def nuevo_pin(existentes) -> str:
    while True:
        p = f"{random.randint(0, 9999):04d}"
        if p not in existentes:
            return p


def admin_parejas(ctx):
    seccion("👥 Parejas de conteo")
    P = leer_parejas()
    with st.form("form_pareja", clear_on_submit=True):
        p1, p2, p3, p4 = st.columns([1.2, 2, 2, 2])
        nombre = p1.text_input("Nombre pareja", placeholder=f"Pareja {len(P) + 1}")
        aux1 = p2.text_input("Auxiliar 1 *")
        aux2 = p3.text_input("Auxiliar 2 *")
        zona = p4.selectbox("Zona asignada", list(ZONAS))
        gond = st.text_input("Góndolas / ubicaciones asignadas")
        if st.form_submit_button("➕ Crear pareja (genera PIN)", type="primary"):
            nom = nombre.strip() or f"Pareja {len(P) + 1}"
            if not aux1.strip() or not aux2.strip():
                st.error("Indique los dos auxiliares.")
            elif not P.empty and nom in set(P["nombre"]):
                st.error("Ya existe una pareja con ese nombre.")
            else:
                pin = nuevo_pin(set(P["pin"]) if not P.empty else set())
                ejecutar(insert(T_PAR).values(id=uuid.uuid4().hex[:10], nombre=nom, aux1=aux1.strip(), aux2=aux2.strip(),
                                              pin=pin, zona=zona, gondolas=gond.strip(), estado="Activa",
                                              inicio=ahora().strftime("%Y-%m-%d %H:%M:%S"), fin=""))
                leer_parejas.clear()
                st.success(f"Pareja **{nom}** creada. PIN: **{pin}** (entrégueselo a la pareja).")
    P = leer_parejas()
    if not P.empty:
        st.caption("Puede editar auxiliares, zona, góndolas, PIN y estado directamente en la tabla.")
        v = P.set_index("id")[["nombre", "aux1", "aux2", "pin", "zona", "gondolas", "estado", "inicio", "fin"]]
        ed = st.data_editor(v, hide_index=True, key=f"ed_par_{len(P)}", disabled=["nombre", "inicio", "fin"],
                            column_config={"estado": st.column_config.SelectboxColumn("estado", options=["Activa", "Finalizada"]),
                                           "zona": st.column_config.SelectboxColumn("zona", options=list(ZONAS)),
                                           "pin": st.column_config.TextColumn("PIN", max_chars=4)})
        for pid_, r in ed.iterrows():
            o = v.loc[pid_]
            cambios = {c: str(r[c]) for c in ["aux1", "aux2", "pin", "zona", "gondolas", "estado"] if str(r[c]) != str(o[c])}
            if cambios:
                if cambios.get("estado") == "Finalizada":
                    cambios["fin"] = ahora().strftime("%Y-%m-%d %H:%M:%S")
                elif cambios.get("estado") == "Activa":
                    cambios["fin"] = ""
                ejecutar(update(T_PAR).where(T_PAR.c.id == pid_).values(**cambios))
                leer_parejas.clear()
                st.rerun()

    seccion("📥 Importar archivo de pistoleo (lector descargado / TPN)")
    with st.form("form_import"):
        i1, i2, i3 = st.columns([2, 1.2, 1.2])
        f = i1.file_uploader("Archivo de pistoleo", type=["xlsx", "xlsm", "csv"])
        par_opc = list(P["nombre"]) if not P.empty else []
        par_sel = i2.selectbox("Pareja que lo contó", ["(sin asignar)"] + par_opc)
        zona_sel = i3.selectbox("Zona", list(ZONAS))
        if st.form_submit_button("Importar lecturas", type="primary") and f is not None:
            data = f.getvalue()
            sha = hashlib.sha256(data).hexdigest()[:20]
            if cfg(f"import_{sha}"):
                st.warning("Ese archivo ya fue importado antes; no se duplicaron lecturas.")
            else:
                pis = leer_pistoleo(data, f.name)
                filas = []
                for _, r in pis.iterrows():
                    ref, lote = r["REFERENCIA"], r["LOTE"]
                    if not ref and r["EAN"]:
                        ref, lc, _, _ = resolver_codigo(r["EAN"], ctx["gtin"])
                        lote = lote or lc
                    filas.append({c.name: "" for c in T_LECT.columns} | dict(
                        id=uuid.uuid4().hex[:16], ts=ahora().strftime("%Y-%m-%d %H:%M:%S"), pareja=par_sel,
                        modo="ARCHIVO", grupo=ZONAS[zona_sel], zona=zona_sel, gondola=str(r["GONDOLA"]),
                        nivel=str(r["NIVEL"]), serial=str(r["SERIAL"]), codigo_leido=str(r["EAN"]), referencia=ref,
                        descripcion=str(r["DESCRIPCION"]), lote=lote,
                        vence=r["VENCE"].strftime("%Y-%m-%d") if not pd.isna(r["VENCE"]) else "",
                        cantidad=float(r["CANTIDAD"]), origen=f"Archivo {f.name}"[:120], anulada=0))
                if filas:
                    ejecutar(insert(T_LECT), filas)
                    cfg_set(f"import_{sha}", f.name)
                    leer_lecturas.clear()
                st.success(f"{len(filas)} lecturas importadas.")

    seccion("📡 Monitor de lecturas en vivo")
    L = leer_lecturas()
    if L.empty:
        st.info("Aún no hay lecturas.")
    else:
        f1, f2, f3, f4 = st.columns([1.5, 1.5, 2, 1.3])
        fp = f1.multiselect("Pareja", sorted(L["pareja"].unique()), placeholder="Todas")
        frev = f4.toggle("🟡 Solo por revisar", key="mon_rev")
        g1, g2 = st.columns(2)
        solo_dob = g1.toggle("🔁 Solo posibles dobles", key="mon_dob")
        ver_elim = g2.toggle("Mostrar también las eliminadas", key="mon_elim")
        fm = f2.multiselect("Modo", sorted(L["modo"].unique()), placeholder="Todos")
        fb = f3.text_input("Buscar referencia / lote / serial")
        d = L
        if fp:
            d = d[d["pareja"].isin(fp)]
        if fm:
            d = d[d["modo"].isin(fm)]
        if frev:
            d = d[d["observacion"].astype(str).str.startswith("⚠ REVISAR")]
        if fb:
            b_ = fb.strip().upper()
            d = d[d["referencia"].str.upper().str.contains(b_, regex=False) | d["lote"].str.upper().str.contains(b_, regex=False)
                  | d["serial"].str.upper().str.contains(b_, regex=False)]
        d = d.sort_values("ts", ascending=False)
        if solo_dob:
            d = d[marcar_posibles_dobles(d) & (d["anulada"] == 0)]
        if not ver_elim:
            d = d[d["anulada"] == 0]
        st.caption(f"{fmt_num(len(d))} lecturas · corrija en las columnas ✏️, marque 🗑️ para eliminar o ↩️ para restaurar, "
                   "y pulse 💾 Guardar cambios.")
        editor_lecturas(d.head(2000), "Administrador", ctx, es_admin=True, clave_ed="mon", alto=400)
        Hc = leer_correcciones()
        with st.expander(f"🕓 Historial de correcciones ({fmt_num(len(Hc))})", expanded=False):
            if Hc.empty:
                st.info("Aún no hay correcciones.")
            else:
                Hx = Hc.merge(L[["id", "pareja", "referencia"]].rename(columns={"id": "lectura_id", "referencia": "ref_actual"}),
                              on="lectura_id", how="left").sort_values("ts", ascending=False)
                st.dataframe(Hx[["ts", "usuario", "pareja", "ref_actual", "campo", "antes", "despues", "lectura_id"]].rename(
                    columns={"ts": "FECHA / HORA", "usuario": "CORRIGIÓ", "pareja": "PAREJA DE LA LECTURA",
                             "ref_actual": "REFERENCIA", "campo": "CAMPO", "antes": "ANTES", "despues": "DESPUÉS",
                             "lectura_id": "ID LECTURA"}), hide_index=True, height=300)

    seccion("🧭 Trazabilidad por pareja")
    traz, det = trazabilidad()
    if not traz.empty:
        st.dataframe(traz, hide_index=True, column_config={
            "% DEL TOTAL": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")})
    st.download_button("⬇️ Informe de Trazabilidad por Parejas (.xlsx)", data=lambda: a_excel(
        excel_traz(traz, det), "INFORME DE TRAZABILIDAD POR PAREJAS DE CONTEO", f"Responsable: {ctx['p']['responsable'] or '—'}"),
        file_name=f"Trazabilidad_Parejas_{ahora():%Y%m%d_%H%M}.xlsx", type="primary", width="stretch",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def trazabilidad():
    L = leer_lecturas()
    if L.empty:
        return pd.DataFrame(), pd.DataFrame()
    Lv = L[L["anulada"] == 0]
    P = leer_parejas()
    aux = dict(zip(P["nombre"], P["aux1"] + " / " + P["aux2"])) if not P.empty else {}
    E = leer_estado_seriales()
    ser_c = E.groupby("pareja")["serial"].count() if not E.empty else pd.Series(dtype=int)
    t = Lv.groupby("pareja", as_index=False).agg(
        ZONAS=("zona", lambda s: ", ".join(sorted(set(s)))), LECTURAS=("id", "count"), UNIDADES=("cantidad", "sum"),
        MANUALES=("modo", lambda s: int((s == "MANUAL").sum())), REFERENCIAS=("referencia", "nunique"),
        SERIALES=("serial", lambda s: len({x for x in s if x})),
        GONDOLAS=("gondola", lambda s: ", ".join(sorted({x for x in s if x}))),
        PRIMER_REGISTRO=("ts", "min"), ULTIMO_REGISTRO=("ts", "max"))
    t.insert(1, "AUXILIARES", t["pareja"].map(aux).fillna("—"))
    t["SERIALES_CERRADOS"] = t["pareja"].map(ser_c).fillna(0).astype(int)
    t["ANULADAS"] = t["pareja"].map(L[L["anulada"] == 1].groupby("pareja")["id"].count()).fillna(0).astype(int)
    t["% DEL TOTAL"] = (t["UNIDADES"] / max(t["UNIDADES"].sum(), 1) * 100).round(1)
    return t.rename(columns={"pareja": "PAREJA"}).sort_values("UNIDADES", ascending=False), L


def excel_traz(traz, L) -> dict:
    P = leer_parejas().drop(columns=["pin", "id"], errors="ignore")
    E = leer_estado_seriales()
    Hc = leer_correcciones()
    hojas = {"Resumen_por_Pareja": traz, "Parejas": P, "Lecturas_Todas": L if not L.empty else L,
             "Seriales_Cerrados": E, "Historial_Correcciones": Hc}
    if not L.empty:
        Lv = L[L["anulada"] == 0]
        hojas["Pareja_x_Gondola"] = Lv.pivot_table(index=["pareja", "zona", "gondola"], values="cantidad", aggfunc="sum").reset_index()
    return hojas


def admin_seriales(ctx):
    S, U = ctx["S"], ctx["U"]
    if S.empty:
        st.info("Cargue el NAL para ver los seriales.")
        return
    L = lecturas_validas()
    Se = estado_seriales(S, L)
    g1, g2, g3 = st.columns([1, 1, 2])
    gr = g1.selectbox("Grupo", ["SMITH", "SERENA"], key="ser_grupo")
    est = g2.multiselect("Estado", ["⏳ PENDIENTE", "🔄 EN CONTEO", "✅ CERRADO"], placeholder="Todos")
    bus = g3.text_input("Buscar serial / set", key="ser_bus")
    d = Se[Se["GRUPO"] == gr]
    tot = len(d)
    k = st.columns(4)
    for col, (e, colr) in zip(k, [("⏳ PENDIENTE", C["rojo"]), ("🔄 EN CONTEO", C["ambar"]), ("✅ CERRADO", C["verde"])]):
        n = int((d["ESTADO"] == e).sum())
        kpi(col, e, fmt_num(n), f"{pct(n, tot):.1f}% de {fmt_num(tot)} seriales", colr, pct(n, tot))
    kpi(k[3], "Unidades en seriales", fmt_num(d["UNIDADES"].sum()), f"contadas: {fmt_num(d['CONTADO'].sum())}", C["navy"])
    if est:
        d = d[d["ESTADO"].isin(est)]
    if bus:
        b_ = bus.strip().upper()
        d = d[d["SERIAL"].str.contains(b_, regex=False) | d["SET"].str.upper().str.contains(b_, regex=False)]
    d = d.assign(DIFERENCIA=d["CONTADO"] - d["UNIDADES"])
    st.dataframe(d[["SERIAL", "SET", "BODEGA_NOM", "ORIGEN_BOD", "ESTADO", "LINEAS", "UNIDADES", "CONTADO", "DIFERENCIA",
                    "PAREJAS", "CERRADO_POR", "CERRADO_TS", "ULTIMA"]], hide_index=True, height=360)
    ser_det = st.selectbox("Ver detalle de un serial", ["—"] + list(d["SERIAL"]), key="ser_det")
    if ser_det != "—":
        M = comparar(U[U["SERIAL"] == ser_det], L[L["SERIAL"] == ser_det], gr, ctx["p"]["base_valor"], Se)
        mostrar_tabla(M.drop(columns=["TIPO", "BODEGAS", "ORIGEN"]), alto=320)
        r = Se[Se["SERIAL"] == ser_det].iloc[0]
        if r["ESTADO"] == "✅ CERRADO" and st.button("↩️ Reabrir este serial"):
            fijar_estado_serial(ser_det, gr, None)
            st.rerun()
    no_list = L[(L["SERIAL"] != "") & ~L["SERIAL"].isin(set(S["SERIAL"]))]
    if not no_list.empty:
        seccion("🆕 Seriales escaneados que no están en el NAL")
        st.dataframe(no_list.groupby("SERIAL", as_index=False).agg(LECTURAS=("id", "count"), UNIDADES=("cantidad", "sum"),
                                                                   PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s))))),
                     hide_index=True)


CATEGORIA = {
    "✅ CUADRADO": "Cuadrado", "🔻 FALTANTE": "Faltante", "🔻 FALTANTE (NO ENCONTRADO)": "Faltante",
    "🔺 SOBRANTE": "Sobrante", "⚠️ LOTE / UBICACIÓN NO COINCIDE": "Novedad", "🆕 REFERENCIA NO LISTADA": "Novedad",
    "🆕 SERIAL NO LISTADO": "Novedad", "⏳ SERIAL PENDIENTE": "Pendiente", "⏳ POR CONTAR": "Pendiente",
}
CAT_COLOR = {"Cuadrado": C["verde"], "Faltante": C["rojo"], "Sobrante": C["ambar"], "Novedad": "#8E6CCF",
             "Pendiente": "#C9D3E0"}
CAT_ICONO = {"Cuadrado": "✅", "Faltante": "🔻", "Sobrante": "🔺", "Novedad": "🆕", "Pendiente": "⏳"}
OPC_CONCILIACION = ["Sin revisar", "Justificada", "Justificada con gasto", "Ajustar en sistema", "Recontar",
                    "En investigación", "Cerrada"]


def firma_parametros() -> tuple:
    p = parametros()
    return (sha_de("nal"), sha_de("valref"), sha_de("templete"), sha_de("tpn"), sha_de("serena"),
            p["criterio"], p["incluir_otras"], p["dias"], p["base_valor"], p["hoja_tpl"], p["hoja_ser"],
            p["solo_implantes"], conteo_cerrado())


@st.cache_data(max_entries=8, show_spinner="Calculando el cruce…")
def cruce_cache(grupo: str, version: str, firma: tuple):
    """Cruce completo de un grupo. Se recalcula solo cuando cambian las lecturas o los parámetros."""
    ctx = contexto()
    L = lecturas_validas()
    Se = estado_seriales(ctx["S"], L) if not ctx["S"].empty else ctx["S"]
    M = comparar_grupo(ctx, L, grupo, Se)
    if not M.empty:
        M["CATEGORIA"] = M["ESTADO"].map(CATEGORIA).fillna("Novedad")
    return M, Se


def obtener_cruce(grupo: str):
    return cruce_cache(grupo, version_datos(), firma_parametros())


def _resultado(esperado, contado, solo_pend):
    esperado = pd.to_numeric(esperado, errors="coerce").fillna(0).to_numpy()
    contado = pd.to_numeric(contado, errors="coerce").fillna(0).to_numpy()
    solo_pend = pd.Series(solo_pend).fillna(False).astype(bool).to_numpy()
    dif = contado - esperado
    abierto = not conteo_cerrado()
    return np.select([esperado == 0, dif == 0, solo_pend, (contado == 0) & abierto, dif < 0],
                     ["Novedad", "Cuadrado", "Pendiente", "Pendiente", "Faltante"], "Sobrante")


def cruce_agregado(M: pd.DataFrame, nivel: str) -> pd.DataFrame:
    """nivel = 'REF' (referencia y cantidades) o 'REFLOTE' (referencia + lote y cantidades)."""
    if M is None or M.empty:
        return pd.DataFrame()
    llaves = ["K_REF"] if nivel == "REF" else ["K_REF", "K_LOTE"]
    agg = dict(REFERENCIA=("REFERENCIA", "first"), DESCRIPCION=("DESCRIPCION", "first"),
               ESPERADO=("SISTEMA", "sum"), CONTADO=("CONTADO", "sum"), COSTO_UNIT=("COSTO_UNIT", "max"),
               PAREJAS=("PAREJAS", lambda x: ", ".join(sorted({p for v in x for p in str(v).split(", ") if p}))),
               SOLO_PEND=("CATEGORIA", lambda x: set(x) <= {"Pendiente"}),
               SERIALES=("SERIAL", lambda x: ", ".join(sorted({p for v in x for p in str(v).split(", ") if p})[:8])))
    if nivel == "REF":
        agg["LOTES"] = ("K_LOTE", "nunique")
    else:
        agg.update(LOTE=("LOTE", "first"), VENCE=("VENCE", "min"), ESTADO_VENC=("ESTADO_VENC", "first"),
                   GONDOLAS=("GONDOLAS", lambda x: ", ".join(sorted({p for v in x for p in str(v).split(", ") if p}))))
    R = M.groupby(llaves, as_index=False).agg(**agg)
    if nivel == "REF":
        R["K_LOTE"] = ""
    R["DIFERENCIA"] = R["CONTADO"] - R["ESPERADO"]
    R["% CONTADO"] = np.where(R["ESPERADO"] > 0, np.minimum(R["CONTADO"], R["ESPERADO"]) / R["ESPERADO"].where(R["ESPERADO"] > 0, 1) * 100, 0.0)
    R["VALOR_ESPERADO"] = R["ESPERADO"] * R["COSTO_UNIT"]
    R["VALOR_DIF"] = R["DIFERENCIA"] * R["COSTO_UNIT"]
    R["CAT"] = _resultado(R["ESPERADO"], R["CONTADO"], R["SOLO_PEND"])
    R["RESULTADO"] = R["CAT"].map(lambda c: f"{CAT_ICONO[c]} {c}")
    return R


def con_observaciones(R: pd.DataFrame, grupo: str, nivel: str) -> pd.DataFrame:
    O = leer_observaciones()
    R = R.copy()
    R["ID_OBS"] = grupo + "|" + nivel + "|" + R["K_REF"].astype(str) + "|" + R["K_LOTE"].astype(str)
    if O.empty:
        R["OBSERVACION"], R["CONCILIACION"], R["OBS_USUARIO"], R["OBS_FECHA"] = "", "Sin revisar", "", ""
        return R
    o = O.set_index("id")
    R["OBSERVACION"] = R["ID_OBS"].map(o["observacion"]).fillna("")
    R["CONCILIACION"] = R["ID_OBS"].map(o["conciliacion"]).fillna("Sin revisar").replace("", "Sin revisar")
    R["OBS_USUARIO"] = R["ID_OBS"].map(o["usuario"]).fillna("")
    R["OBS_FECHA"] = R["ID_OBS"].map(o["ts"]).fillna("")
    return R


def tabla_conciliacion(R: pd.DataFrame, grupo: str, nivel: str, etq_esp: str, filtro_hash: str):
    """Tabla del cruce con OBSERVACIÓN y CONCILIACIÓN editables; cada cambio se guarda solo."""
    if R.empty:
        st.info("No hay registros para mostrar con esta selección.")
        return
    cols = ["RESULTADO", "REFERENCIA"] + (["LOTE"] if nivel == "REFLOTE" else []) + \
           ["ESPERADO", "CONTADO", "DIFERENCIA"] + (["GASTO", "DIF_TRAS_GASTO"] if "GASTO" in R.columns else []) + \
           ["CONCILIACION", "OBSERVACION", "VALOR_DIF", "DESCRIPCION"] + \
           (["VENCE"] if nivel == "REFLOTE" else ["LOTES"]) + ["% CONTADO", "OBS_USUARIO"]
    v = R.set_index("ID_OBS")[cols].copy()
    for c in ("ESPERADO", "CONTADO", "DIFERENCIA", "VALOR_DIF", "GASTO", "DIF_TRAS_GASTO"):
        if c in v.columns:
            v[c] = pd.to_numeric(v[c], errors="coerce").round(0)
    if "VENCE" in v.columns:
        v["VENCE"] = pd.to_datetime(v["VENCE"])
    ver = st.session_state.get(f"obsver_{grupo}_{nivel}", 0)
    clave_ed = f"conc_{grupo}_{nivel}_{ver}_{filtro_hash}_{hash(tuple(v.index)) % 10**8}"
    ed = st.data_editor(
        v, key=clave_ed, hide_index=True, height=480, num_rows="fixed",
        disabled=[c for c in v.columns if c not in ("CONCILIACION", "OBSERVACION")],
        column_config={
            "RESULTADO": st.column_config.TextColumn("RESULTADO", width="small"),
            "DESCRIPCION": st.column_config.TextColumn("DESCRIPCIÓN", width="medium"),
            "REFERENCIA": st.column_config.TextColumn("REFERENCIA", pinned=True),
            "VENCE": st.column_config.DateColumn("VENCE", format="DD/MM/YYYY"),
            "LOTES": st.column_config.NumberColumn("LOTES", format="%d"),
            "CONTADO": st.column_config.NumberColumn("CONTADO", format="localized"),
            "DIFERENCIA": st.column_config.NumberColumn("DIFERENCIA", format="localized"),
            "% CONTADO": st.column_config.ProgressColumn("% CONTADO", min_value=0, max_value=100, format="%.0f%%"),
            "VALOR_DIF": st.column_config.NumberColumn("VALOR DIF. $", format="localized"),
            "CONCILIACION": st.column_config.SelectboxColumn("CONCILIACIÓN ✏️", options=OPC_CONCILIACION, required=True),
            "OBSERVACION": st.column_config.TextColumn("OBSERVACIÓN ✏️", width="large", max_chars=500),
            "ESPERADO": st.column_config.NumberColumn(etq_esp, format="localized", width="small"),
            "OBS_USUARIO": st.column_config.TextColumn("REVISÓ"),
            "GASTO": st.column_config.NumberColumn("GASTOS (UND)", format="%d", help="Consumos de cirugía de esa referencia/lote"),
            "DIF_TRAS_GASTO": st.column_config.NumberColumn("QUEDA TRAS GASTOS", format="%d"),
        })
    dif = (ed["OBSERVACION"].fillna("").astype(str) != v["OBSERVACION"].fillna("").astype(str)) | \
          (ed["CONCILIACION"].fillna("").astype(str) != v["CONCILIACION"].fillna("").astype(str))
    if dif.any():
        cambios = []
        for oid in ed.index[dif]:
            g_, n_, kr, kl = oid.split("|", 3)
            cambios.append(dict(grupo=g_, nivel=n_, k_ref=kr, k_lote=kl, observacion=ed.at[oid, "OBSERVACION"] or "",
                                conciliacion=ed.at[oid, "CONCILIACION"] or "Sin revisar"))
        guardar_observaciones(cambios, st.session_state.get("usuario_admin", "Administrador"))
        st.session_state[f"obsver_{grupo}_{nivel}"] = ver + 1
        st.toast(f"💾 {len(cambios)} observación(es) guardada(s)")
        st.rerun()


def barra_composicion(conteos: dict, total: int, clave_graf: str):
    fig = go.Figure()
    for cat in ["Cuadrado", "Faltante", "Sobrante", "Novedad", "Pendiente"]:
        n = conteos.get(cat, 0)
        if n:
            fig.add_bar(y=[""], x=[n], orientation="h", name=f"{CAT_ICONO[cat]} {cat} ({fmt_num(n)})",
                        marker_color=CAT_COLOR[cat],
                        text=f"{cat} {pct(n, total):.0f}%" if pct(n, total) >= 6 else "", textposition="inside",
                        insidetextanchor="middle", hovertemplate=f"{cat}: {n} líneas<extra></extra>")
    fig.update_layout(barmode="stack", height=105, margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                      legend=dict(orientation="h", y=-0.4, x=0, traceorder="normal"), xaxis=dict(visible=False),
                      yaxis=dict(visible=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(size=13))
    st.plotly_chart(fig, key=clave_graf, config={"displayModeBar": False})


def tabla_limpia(df: pd.DataFrame, columnas: dict, alto=460, key=None):
    if df is None or df.empty:
        st.info("No hay registros para mostrar con esta selección.")
        return
    d = df[[c for c in columnas if c in df.columns]].rename(columns=columnas).copy()
    for c in d.columns:
        if "VALOR" in c or c in ("SISTEMA", "CONTADO", "DIFERENCIA"):
            d[c] = pd.to_numeric(d[c], errors="coerce").round(0)
    cfg_cols = {}
    for c in d.columns:
        if c.startswith("%"):
            cfg_cols[c] = st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%.0f%%")
        elif "VALOR" in c or c in ("SISTEMA", "CONTADO", "DIFERENCIA", "LOTES", "SERIALES"):
            cfg_cols[c] = st.column_config.NumberColumn(c, format="localized")
    st.dataframe(d, hide_index=True, height=alto, column_config=cfg_cols, key=key)


def admin_grupo(ctx, grupo: str):
    p = ctx["p"]
    nombre_g = "Smith & Nephew" if grupo == "SMITH" else "Serena del Mar"
    if ctx["U"].empty and lecturas_validas().empty:
        alerta("ℹ️ Cargue el NAL y los templetes en <b>⚙️ Maestros</b> para generar el inventario a contar.", "azul")
        return None
    M, Se = obtener_cruce(grupo)
    ETQ = etq_esperado(ctx, grupo)
    if M.empty:
        st.info("Sin datos para este grupo.")
        return M
    RL = cruce_agregado(M, "REFLOTE")
    RR = cruce_agregado(M, "REF")
    Ms = RL[RL["CAT"] != "Novedad"]
    esp = Ms["ESPERADO"].sum()
    cob = np.minimum(Ms["CONTADO"], Ms["ESPERADO"]).sum()
    falt, sobr, nov = RL[RL["CAT"] == "Faltante"], RL[RL["CAT"] == "Sobrante"], RL[RL["CAT"] == "Novedad"]
    sg = Se[Se["GRUPO"] == grupo] if not Se.empty else Se
    n_ser = len(sg)
    n_cerr = int((sg["ESTADO"] == "✅ CERRADO").sum()) if n_ser else 0
    n_pend = int((sg["ESTADO"] == "⏳ PENDIENTE").sum()) if n_ser else 0

    k = st.columns(5)
    kpi(k[0], "Avance del conteo", f"{pct(cob, esp):.1f}%", f"{fmt_num(cob)} de {fmt_num(esp)} und", C["teal"], pct(cob, esp))
    kpi(k[1], "Seriales cerrados", f"{fmt_num(n_cerr)} / {fmt_num(n_ser)}", f"⏳ {fmt_num(n_pend)} sin empezar", C["navy"],
        pct(n_cerr, n_ser))
    kpi(k[2], "🔻 Faltantes", fmt_num(-falt["DIFERENCIA"].sum()), fmt_cop(falt["VALOR_DIF"].sum()), C["rojo"])
    kpi(k[3], "🔺 Sobrantes", fmt_num(sobr["DIFERENCIA"].sum()), fmt_cop(sobr["VALOR_DIF"].sum()), C["ambar"])
    revisadas = int((RL.loc[RL["CAT"].isin(["Faltante", "Sobrante", "Novedad"])].pipe(
        lambda d: con_observaciones(d, grupo, "REFLOTE")).pipe(
        lambda d: (d["CONCILIACION"] != "Sin revisar") | (d["OBSERVACION"].astype(str).str.strip() != ""))).sum()) if len(RL) else 0
    n_dif = int(RL["CAT"].isin(["Faltante", "Sobrante", "Novedad"]).sum())
    kpi(k[4], "📝 Diferencias conciliadas", f"{fmt_num(revisadas)} / {fmt_num(n_dif)}", f"{fmt_num(len(nov))} novedades",
        "#8E6CCF", pct(revisadas, n_dif))

    st.write("")
    st.markdown(f"**¿Cómo va {nombre_g}?** &nbsp; {fmt_num(len(RL))} referencia·lote · lo contado se compara con **{ETQ}**")
    barra_composicion(RL["CAT"].value_counts().to_dict(), len(RL), f"comp_{grupo}")

    chips = []
    venc = int((Ms["ESTADO_VENC"] == "VENCIDO").sum())
    prox = int((Ms["ESTADO_VENC"] == "PRÓXIMO A VENCER").sum())
    fuera = ctx["UV"]["excl"]
    fuera_g = fuera[fuera["GRUPO"] == grupo] if not fuera.empty else fuera
    L = lecturas_validas()
    lg_ = L[L["grupo"] == grupo] if not L.empty and "observacion" in L.columns else pd.DataFrame()
    n_rev = int(lg_["observacion"].astype(str).str.startswith("⚠ REVISAR").sum()) if not lg_.empty else 0
    if venc:
        chips.append(f'<span class="chip no">⛔ {fmt_num(venc)} lotes vencidos</span>')
    if prox:
        chips.append(f'<span class="chip info">⏰ {fmt_num(prox)} vencen en ≤ {p["dias"]} días</span>')
    if n_rev:
        chips.append(f'<span class="chip no">🟡 {fmt_num(n_rev)} lecturas con lote por revisar</span>')
    if len(fuera_g):
        chips.append(f'<span class="chip info">🔧 {fmt_num(len(fuera_g))} registros fuera de alcance</span>')
    chips.append('<span class="chip ok">🟢 Conteo abierto</span>' if not conteo_cerrado()
                 else '<span class="chip no">🏁 Conteo cerrado</span>')
    st.markdown(" ".join(chips), unsafe_allow_html=True)

    st.write("")
    vistas = ["📦 Cruce por referencia", "🏷️ Cruce por referencia · lote", "🩺 Gastos vs faltantes", "🧰 Por serial",
              "⏰ Vencimientos", "🔧 Fuera de alcance"]
    vista = st.segmented_control("Ver", vistas, default=vistas[0], key=f"vista_{grupo}") or vistas[0]
    c1, c2, c3 = st.columns([2, 2.6, 1.2])
    buscar = c1.text_input("🔎 Buscar referencia, lote, serial o descripción", key=f"bus_{grupo}")
    cats = []
    solo_sin = False
    if vista in vistas[:2]:
        with c2:
            cats = st.pills("Mostrar solo", ["Faltante", "Sobrante", "Novedad", "Pendiente", "Cuadrado"],
                            selection_mode="multi", key=f"cat_{grupo}", format_func=lambda c: f"{CAT_ICONO[c]} {c}") or []
        solo_sin = c3.toggle("Sin conciliar", key=f"sinc_{grupo}", help="Solo diferencias aún 'Sin revisar'")

    def filtrar(d, cols_busca):
        if buscar.strip() and not d.empty:
            b_ = buscar.strip().upper()
            msk = pd.Series(False, index=d.index)
            for c in cols_busca:
                if c in d.columns:
                    msk |= d[c].astype(str).str.upper().str.contains(b_, regex=False)
            d = d[msk]
        return d

    if vista in vistas[:2]:
        nivel = "REF" if vista == vistas[0] else "REFLOTE"
        R = con_observaciones(RR if nivel == "REF" else RL, grupo, nivel)
        if sha_de("gastos"):
            R = con_gastos(R, nivel, gastos_grupo(grupo))
        if cats:
            R = R[R["CAT"].isin(cats)]
        if solo_sin:
            R = R[R["CAT"].isin(["Faltante", "Sobrante", "Novedad"]) & (R["CONCILIACION"] == "Sin revisar")]
        R = filtrar(R, ["REFERENCIA", "DESCRIPCION", "LOTE", "SERIALES", "OBSERVACION"])
        orden = {"Faltante": 0, "Sobrante": 1, "Novedad": 2, "Pendiente": 3, "Cuadrado": 4}
        R = R.assign(_o=R["CAT"].map(orden)).sort_values(["_o", "REFERENCIA"] + (["LOTE"] if nivel == "REFLOTE" else []))
        st.caption(f"{fmt_num(len(R))} filas · escriba en **OBSERVACIÓN ✏️** y elija el estado en **CONCILIACIÓN ✏️**: "
                   "se guarda solo y queda en el Excel.")
        tabla_conciliacion(R, grupo, nivel, ETQ, f"{hash((tuple(cats), solo_sin, buscar)) % 10**6}")
    elif vista == "🩺 Gastos vs faltantes":
        vista_gastos(ctx, grupo, RR, RL, buscar)
    elif vista == "🧰 Por serial":
        if sg.empty:
            st.info("No hay seriales en este grupo.")
        else:
            D = sg.copy()
            D["DIFERENCIA"] = D["CONTADO"] - D["UNIDADES"]
            D["% CONTADO"] = np.where(D["UNIDADES"] > 0, np.minimum(D["CONTADO"], D["UNIDADES"]) / D["UNIDADES"] * 100, 0.0)
            D = filtrar(D, ["SERIAL", "SET", "BODEGA_NOM", "PAREJAS"]).sort_values(["ESTADO", "SERIAL"])
            st.caption(f"{fmt_num(len(D))} seriales del NAL · qué falta por contar")
            tabla_limpia(D, {"ESTADO": "ESTADO", "SERIAL": "SERIAL", "SET": "SET", "BODEGA_NOM": "BODEGA",
                             "UNIDADES": "SISTEMA", "CONTADO": "CONTADO", "DIFERENCIA": "DIFERENCIA",
                             "% CONTADO": "% CONTADO", "PAREJAS": "PAREJA(S)", "CERRADO_POR": "CERRADO POR"},
                         key=f"t_ser_{grupo}")
    elif vista == "⏰ Vencimientos":
        D = filtrar(RL[RL["ESTADO_VENC"].isin(["VENCIDO", "PRÓXIMO A VENCER"])].sort_values("VENCE"),
                    ["REFERENCIA", "DESCRIPCION", "LOTE"])
        tabla_limpia(D, {"ESTADO_VENC": "ESTADO VENC.", "VENCE": "VENCE", "REFERENCIA": "REFERENCIA",
                         "DESCRIPCION": "DESCRIPCIÓN", "LOTE": "LOTE", "ESPERADO": "SISTEMA", "CONTADO": "CONTADO",
                         "DIFERENCIA": "DIFERENCIA"}, alto=420, key=f"t_ven_{grupo}")
    else:
        D = filtrar(fuera_g, ["REFERENCIA", "DESCRIPCION", "SERIAL", "SET", "MOTIVO"])
        st.caption("Estos registros del NAL NO se cuentan: instrumental, referencias fuera del templete o con * / **.")
        if not D.empty:
            st.dataframe(D.groupby("MOTIVO", as_index=False).agg(REGISTROS=("REFERENCIA", "count"),
                                                                  UNIDADES=("CANTIDAD", "sum")), hide_index=True)
        st.dataframe(D, hide_index=True, height=360)

    st.write("")
    titulo = "CONCILIACIÓN DE INVENTARIO · SMITH & NEPHEW" if grupo == "SMITH" else "CONCILIACIÓN DE INVENTARIO · SERENA DEL MAR"
    nombre = "Conciliacion_Smith" if grupo == "SMITH" else "Conciliacion_Serena_del_Mar"
    panel_importar_excel(grupo)
    st.download_button(f"⬇️ Descargar Excel de conciliación · {nombre_g}", type="primary", width="stretch",
                       data=lambda: excel_conciliacion(ctx, grupo),
                       file_name=f"{nombre}_{ahora():%Y%m%d_%H%M}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{grupo}")
    return M


# =============================================================================
# EXCEL CORPORATIVO (logo, colores Tecnitrauma, portada con indicadores)
# =============================================================================
XC = dict(navy="#0B2545", azul="#2A88C9", azul_claro="#EAF3FA", gris="#F4F6FA", gris_borde="#C9D3E0",
          rojo="#FDECEC", rojo_txt="#B42318", ambar="#FFF1D6", ambar_txt="#9A5B00", verde="#E3F4EF",
          verde_txt="#13795B", morado="#EFE8FB", morado_txt="#5B3A9E", texto="#1B2A41")
_EMO = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍ℹ⏰-⏺↔-⇿]")
_MONEDA = ("VALOR", "COSTO", "$")
_SUMABLES = ("ESPERADO", "SISTEMA", "CONTADO", "DIFERENCIA", "VALOR", "UNIDADES", "CANTIDAD", "TEMPLETE", "LECTURAS",
             "LÍNEAS", "REGISTROS")


def _logo_bytes() -> io.BytesIO:
    return io.BytesIO(base64.b64decode(LOGO_TECNITRAUMA_B64))


def _limpio(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = pd.to_datetime(d[c]).dt.tz_localize(None) if getattr(d[c].dt, "tz", None) else d[c]
        elif d[c].dtype == object or str(d[c].dtype).startswith(("str", "string")):
            d[c] = d[c].astype(object).where(d[c].notna(), "")
            d[c] = d[c].map(lambda x: _EMO.sub("", x).strip() if isinstance(x, str) else x)
        elif str(d[c].dtype) in ("Int64", "Float64", "boolean"):
            d[c] = d[c].astype(object).where(d[c].notna(), None)
    d.columns = unicos([_EMO.sub("", str(c)).strip() for c in d.columns])
    return d


def _formatos(wb):
    F = {}
    F["titulo"] = wb.add_format({"bold": True, "font_size": 17, "font_color": XC["navy"], "valign": "vcenter"})
    F["sub"] = wb.add_format({"font_size": 10, "font_color": "#5A6B85", "valign": "vcenter"})
    F["banda"] = wb.add_format({"bg_color": XC["azul"]})
    F["meta"] = wb.add_format({"font_size": 9, "italic": True, "font_color": "#5A6B85"})
    F["hdr"] = wb.add_format({"bold": True, "bg_color": XC["navy"], "font_color": "#FFFFFF", "border": 1,
                              "border_color": XC["navy"], "text_wrap": True, "valign": "vcenter", "align": "center",
                              "font_size": 10})
    F["int"] = wb.add_format({"num_format": "#,##0;[Red]-#,##0", "font_size": 10})
    F["dec"] = wb.add_format({"num_format": "#,##0.0", "font_size": 10})
    F["money"] = wb.add_format({"num_format": '"$" #,##0;[Red]-"$" #,##0', "font_size": 10})
    F["pct"] = wb.add_format({"num_format": "0%", "font_size": 10})
    F["txt"] = wb.add_format({"font_size": 10, "valign": "top"})
    F["wrap"] = wb.add_format({"font_size": 10, "text_wrap": True, "valign": "top"})
    F["fecha"] = wb.add_format({"num_format": "dd/mm/yyyy", "font_size": 10, "align": "center"})
    F["tot_lbl"] = wb.add_format({"bold": True, "bg_color": XC["azul_claro"], "top": 2, "top_color": XC["navy"], "font_size": 10})
    F["tot_int"] = wb.add_format({"bold": True, "bg_color": XC["azul_claro"], "top": 2, "top_color": XC["navy"],
                                  "num_format": "#,##0;[Red]-#,##0", "font_size": 10})
    F["tot_money"] = wb.add_format({"bold": True, "bg_color": XC["azul_claro"], "top": 2, "top_color": XC["navy"],
                                    "num_format": '"$" #,##0;[Red]-"$" #,##0', "font_size": 10})
    F["banda_fila"] = wb.add_format({"bg_color": XC["gris"]})
    F["c_rojo"] = wb.add_format({"bg_color": XC["rojo"], "font_color": XC["rojo_txt"], "bold": True})
    F["c_ambar"] = wb.add_format({"bg_color": XC["ambar"], "font_color": XC["ambar_txt"], "bold": True})
    F["c_verde"] = wb.add_format({"bg_color": XC["verde"], "font_color": XC["verde_txt"], "bold": True})
    F["c_morado"] = wb.add_format({"bg_color": XC["morado"], "font_color": XC["morado_txt"], "bold": True})
    F["c_gris"] = wb.add_format({"bg_color": "#ECEFF4", "font_color": "#5A6B85"})
    F["f_neg"] = wb.add_format({"font_color": XC["rojo_txt"], "bold": True})
    F["f_pos"] = wb.add_format({"font_color": XC["ambar_txt"], "bold": True})
    F["fila_venc"] = wb.add_format({"bg_color": "#F8D7DA", "font_color": "#842029"})
    F["fila_prox"] = wb.add_format({"bg_color": "#FFE8C2"})
    F["sin_rev"] = wb.add_format({"italic": True, "font_color": "#7A8AA0"})
    # Portada
    F["kpi_t"] = wb.add_format({"font_size": 9, "bold": True, "font_color": "#5A6B85", "bg_color": "#FFFFFF",
                                "left": 5, "left_color": XC["azul"], "top": 1, "top_color": XC["gris_borde"],
                                "right": 1, "right_color": XC["gris_borde"], "valign": "bottom"})
    F["kpi_v"] = wb.add_format({"font_size": 20, "bold": True, "font_color": XC["navy"], "bg_color": "#FFFFFF",
                                "left": 5, "left_color": XC["azul"], "right": 1, "right_color": XC["gris_borde"],
                                "valign": "vcenter"})
    F["kpi_s"] = wb.add_format({"font_size": 9, "font_color": "#7A8AA0", "bg_color": "#FFFFFF", "left": 5,
                                "left_color": XC["azul"], "bottom": 1, "bottom_color": XC["gris_borde"],
                                "right": 1, "right_color": XC["gris_borde"], "valign": "top"})
    F["sec"] = wb.add_format({"bold": True, "font_size": 12, "font_color": XC["navy"], "bottom": 2,
                              "bottom_color": XC["azul"]})
    F["meta_k"] = wb.add_format({"bold": True, "font_size": 10, "font_color": XC["navy"], "bg_color": XC["azul_claro"],
                                 "border": 1, "border_color": XC["gris_borde"]})
    F["meta_v"] = wb.add_format({"font_size": 10, "border": 1, "border_color": XC["gris_borde"], "text_wrap": True})
    return F


def _encabezado(ws, F, titulo, subtitulo, ncols, fila_meta=True):
    ws.set_row(0, 30)
    ws.set_row(1, 22)
    ws.set_row(2, 4)
    ws.insert_image(0, 0, "logo.png", {"image_data": _logo_bytes(), "x_scale": 0.62, "y_scale": 0.62,
                                       "x_offset": 4, "y_offset": 6, "object_position": 3})
    ult = max(ncols - 1, 4)
    ws.merge_range(0, 2, 0, ult, titulo, F["titulo"])
    ws.merge_range(1, 2, 1, ult, subtitulo, F["sub"])
    for j in range(0, ult + 1):
        ws.write_blank(2, j, None, F["banda"])
    if fila_meta:
        ws.write(3, 0, f"Generado: {ahora():%d/%m/%Y %H:%M} · Tecnitrauma · Control de Inventario Físico", F["meta"])


def _ancho(serie: pd.Series, nombre: str) -> float:
    m = serie.astype(str).head(500).str.len()
    base = max(len(str(nombre)) * 1.05, (m.quantile(0.9) if len(m) else 8))
    if "OBSERV" in nombre.upper():
        return 55
    if "DESCRIP" in nombre.upper():
        return min(max(base + 2, 30), 48)
    return min(max(base + 2, 9), 40)


def _hoja_datos(xw, F, nombre, df, titulo, subtitulo, totales=True):
    wb = xw.book
    hoja = re.sub(r"[\[\]\:\*\?\/\\]", "", nombre)[:31]
    df = _limpio(df if df is not None and len(df) else pd.DataFrame({"MENSAJE": ["Sin registros para esta sección"]}))
    df = df.reset_index(drop=True)
    FILA_H = 5
    df.to_excel(xw, sheet_name=hoja, startrow=FILA_H, index=False)
    ws = xw.sheets[hoja]
    ws.hide_gridlines(2)
    cols = list(df.columns)
    n = len(df)
    _encabezado(ws, F, titulo, subtitulo, len(cols))
    ws.set_row(FILA_H, 34)
    from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell
    for j, c in enumerate(cols):
        ws.write(FILA_H, j, c, F["hdr"])
        cu = c.upper()
        if any(k in cu for k in _MONEDA):
            fmt = F["money"]
        elif cu.startswith("%"):
            fmt = F["pct"]
        elif pd.api.types.is_datetime64_any_dtype(df[c]) or cu in ("VENCE", "VENCIMIENTO"):
            fmt = F["fecha"]
        elif pd.api.types.is_numeric_dtype(df[c]):
            fmt = F["int"] if (df[c].dropna() % 1 == 0).all() else F["dec"]
        elif "OBSERV" in cu or "DESCRIP" in cu:
            fmt = F["wrap"]
        else:
            fmt = F["txt"]
        ws.set_column(j, j, _ancho(df[c], c), fmt)
    if n:
        r0, r1, c1 = FILA_H + 1, FILA_H + n, len(cols) - 1
        def col_letra(nombre_col):
            return xl_col_to_name(cols.index(nombre_col))
        # Filas vencidas / próximas a vencer
        for cand in ("ESTADO VENC.", "ESTADO_VENC"):
            if cand in cols:
                L_ = col_letra(cand)
                ws.conditional_format(r0, 0, r1, c1, {"type": "formula", "criteria": f'=${L_}{r0 + 1}="VENCIDO"', "format": F["fila_venc"]})
                ws.conditional_format(r0, 0, r1, c1, {"type": "formula", "criteria": f'=${L_}{r0 + 1}="PRÓXIMO A VENCER"', "format": F["fila_prox"]})
        # Resultado / estado con color por categoría
        for cand in ("RESULTADO", "ESTADO"):
            if cand in cols:
                j = cols.index(cand)
                for txt, f in [("Faltante", "c_rojo"), ("FALTANTE", "c_rojo"), ("Sobrante", "c_ambar"), ("SOBRANTE", "c_ambar"),
                               ("Novedad", "c_morado"), ("NO LISTAD", "c_morado"), ("NO COINCIDE", "c_morado"),
                               ("Cuadrado", "c_verde"), ("CUADRADO", "c_verde"), ("CERRADO", "c_verde"),
                               ("Pendiente", "c_gris"), ("PENDIENTE", "c_gris"), ("POR CONTAR", "c_gris"), ("EN CONTEO", "c_ambar")]:
                    ws.conditional_format(r0, j, r1, j, {"type": "text", "criteria": "containing", "value": txt, "format": F[f]})
        if "CONCILIACIÓN" in cols:
            j = cols.index("CONCILIACIÓN")
            ws.conditional_format(r0, j, r1, j, {"type": "cell", "criteria": "==", "value": '"Sin revisar"', "format": F["sin_rev"]})
            ws.conditional_format(r0, j, r1, j, {"type": "cell", "criteria": "!=", "value": '"Sin revisar"', "format": F["c_verde"]})
            ws.data_validation(r0, j, r1, j, {"validate": "list", "source": OPC_CONCILIACION})
        for cand in ("DIFERENCIA", "DIF. (LOT - COM)"):
            if cand in cols:
                j = cols.index(cand)
                ws.conditional_format(r0, j, r1, j, {"type": "cell", "criteria": "<", "value": 0, "format": F["f_neg"]})
                ws.conditional_format(r0, j, r1, j, {"type": "cell", "criteria": ">", "value": 0, "format": F["f_pos"]})
        if "% CONTADO" in cols:
            j = cols.index("% CONTADO")
            ws.conditional_format(r0, j, r1, j, {"type": "data_bar", "bar_color": XC["azul"], "bar_solid": True,
                                                 "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})
        ws.conditional_format(r0, 0, r1, c1, {"type": "formula", "criteria": f"=MOD(ROW(),2)=0", "format": F["banda_fila"]})
        ws.autofilter(FILA_H, 0, r1, c1)
        # Totales (SUBTOTAL respeta los filtros)
        if totales:
            fila_t = r1 + 1
            hubo = False
            for j, c in enumerate(cols):
                cu = c.upper()
                if pd.api.types.is_numeric_dtype(df[c]) and any(k in cu for k in _SUMABLES) and not cu.startswith("%") \
                        and "COSTO" not in cu:
                    rng = f"{xl_rowcol_to_cell(r0, j)}:{xl_rowcol_to_cell(r1, j)}"
                    ws.write_formula(fila_t, j, f"=SUBTOTAL(109,{rng})",
                                     F["tot_money"] if any(k in cu for k in _MONEDA) else F["tot_int"])
                    hubo = True
                else:
                    ws.write_blank(fila_t, j, None, F["tot_lbl"])
            if hubo:
                ws.write(fila_t, 0, "TOTAL (filas visibles)", F["tot_lbl"])
    ws.freeze_panes(FILA_H + 1, 2 if len(cols) > 4 else 0)
    ws.set_landscape()
    ws.set_paper(1)
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(FILA_H)
    ws.set_margins(left=0.4, right=0.4, top=0.6, bottom=0.6)
    ws.set_header(f"&L&8Tecnitrauma · Inventario Smith & Nephew&R&8{titulo[:60]}")
    ws.set_footer("&L&8Generado &D &T&R&8Página &P de &N")
    return ws


def _portada(xw, F, titulo, subtitulo, meta, kpis, tablas, grafico=None):
    wb = xw.book
    ws = wb.add_worksheet("Resumen")
    xw.sheets["Resumen"] = ws
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 2)
    ws.set_column(1, 12, 15.5)
    ws.set_row(0, 34)
    ws.set_row(1, 22)
    ws.insert_image(0, 1, "logo.png", {"image_data": _logo_bytes(), "x_scale": 0.85, "y_scale": 0.85, "x_offset": 2,
                                       "y_offset": 4, "object_position": 3})
    ws.merge_range(0, 4, 0, 12, titulo, F["titulo"])
    ws.merge_range(1, 4, 1, 12, subtitulo, F["sub"])
    for j in range(0, 13):
        ws.write_blank(2, j, None, F["banda"])
    ws.set_row(2, 4)
    fila = 4
    # Indicadores (tarjetas de 3 columnas x 3 filas)
    for idx, (t, v, s_) in enumerate(kpis):
        r = fila + (idx // 4) * 4
        c = 1 + (idx % 4) * 3
        ws.merge_range(r, c, r, c + 2, t.upper(), F["kpi_t"])
        ws.merge_range(r + 1, c, r + 1, c + 2, v, F["kpi_v"])
        ws.merge_range(r + 2, c, r + 2, c + 2, s_, F["kpi_s"])
        ws.set_row(r + 1, 30)
    fila += ((len(kpis) + 3) // 4) * 4 + 1
    # Datos del corte
    ws.merge_range(fila, 1, fila, 12, "DATOS DEL CORTE", F["sec"])
    fila += 1
    for k_, v_ in meta:
        ws.merge_range(fila, 1, fila, 3, k_, F["meta_k"])
        ws.merge_range(fila, 4, fila, 12, str(v_), F["meta_v"])
        fila += 1
    fila += 1
    # Tablas resumen
    for t, df in tablas:
        if df is None or df.empty:
            continue
        df = _limpio(df)
        ws.merge_range(fila, 1, fila, 12, t.upper(), F["sec"])
        fila += 1
        cols = list(df.columns)
        anchos = [3 if i == 0 else max(1, min(4, int(round(9 / max(len(cols) - 1, 1))))) for i in range(len(cols))]
        if len(cols) == 1:
            anchos = [12]
        c = 1
        posiciones = []
        for j, col in enumerate(cols):
            w = anchos[j]
            if c + w - 1 > 12:
                w = 12 - c + 1
            posiciones.append((c, c + w - 1))
            if w > 1:
                ws.merge_range(fila, c, fila, c + w - 1, col, F["hdr"])
            else:
                ws.write(fila, c, col, F["hdr"])
            c += w
        fila += 1
        for _, rr in df.iterrows():
            for j, col in enumerate(cols):
                a, b = posiciones[j]
                val = rr[col]
                cu = col.upper()
                if isinstance(val, (int, float, np.integer, np.floating)) and not pd.isna(val):
                    fmt = F["money"] if any(k in cu for k in _MONEDA) else (F["pct"] if cu.startswith("%") else F["int"])
                else:
                    fmt = F["txt"]
                    val = "" if (val is None or (not isinstance(val, str) and pd.isna(val))) else val
                if b > a:
                    ws.merge_range(fila, a, fila, b, val, fmt)
                else:
                    ws.write(fila, a, val, fmt)
            fila += 1
        fila += 1
    if grafico:
        etiquetas, valores, colores = grafico
        hoja_aux = "_datos_grafico"
        wa = wb.add_worksheet(hoja_aux)
        wa.hide()
        for i, (e, v) in enumerate(zip(etiquetas, valores)):
            wa.write(i, 0, e)
            wa.write(i, 1, v)
        ch = wb.add_chart({"type": "doughnut"})
        ch.add_series({"name": "Resultado del cruce", "categories": [hoja_aux, 0, 0, len(etiquetas) - 1, 0],
                       "values": [hoja_aux, 0, 1, len(etiquetas) - 1, 1],
                       "points": [{"fill": {"color": c_}} for c_ in colores],
                       "data_labels": {"percentage": True, "value": False, "category": False, "series_name": False,
                                       "font": {"bold": True, "color": "#0B2545", "size": 9}}})
        ch.set_title({"name": "Resultado del cruce (referencia · lote)", "name_font": {"size": 11, "color": XC["navy"]}})
        ch.set_legend({"position": "right"})
        ch.set_hole_size(55)
        ch.set_size({"width": 560, "height": 300})
        ws.insert_chart(4, 14, ch)
    ws.set_landscape()
    ws.set_paper(1)
    ws.fit_to_pages(1, 0)
    ws.set_footer("&L&8Tecnitrauma · Control de Inventario Físico&R&8Página &P de &N")
    ws.activate()


def excel_corporativo(hojas: dict, titulo: str, subtitulo: str = "", portada: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as xw:
        wb = xw.book
        wb.set_properties({"title": titulo, "company": "Tecnitrauma", "author": "Control de Inventario Físico"})
        F = _formatos(wb)
        if portada:
            _portada(xw, F, titulo, subtitulo, portada.get("meta", []), portada.get("kpis", []),
                     portada.get("tablas", []), portada.get("grafico"))
        for nombre, df in hojas.items():
            if portada and nombre == "Resumen":
                continue
            if nombre.startswith("_"):
                df.to_excel(xw, sheet_name=nombre[:31], index=False)
                xw.sheets[nombre[:31]].hide()
                continue
            es_kv = df is not None and list(df.columns) == ["INDICADOR", "VALOR"]
            _hoja_datos(xw, F, nombre, df, titulo, f"{subtitulo} · {nombre.replace('_', ' ')}", totales=not es_kv)
    return buf.getvalue()


def a_excel(hojas: dict, titulo: str, subtitulo: str = "") -> bytes:
    """Todas las descargas usan el formato corporativo."""
    return excel_corporativo(hojas, titulo, subtitulo)


def excel_conciliacion(ctx, grupo: str) -> bytes:
    p = ctx["p"]
    M, Se = obtener_cruce(grupo)
    ETQ = etq_esperado(ctx, grupo)
    nombre_g = "Smith & Nephew" if grupo == "SMITH" else "Serena del Mar"
    RL = con_observaciones(cruce_agregado(M, "REFLOTE"), grupo, "REFLOTE") if not M.empty else pd.DataFrame()
    RR = con_observaciones(cruce_agregado(M, "REF"), grupo, "REF") if not M.empty else pd.DataFrame()
    sg = Se[Se["GRUPO"] == grupo] if Se is not None and not Se.empty else pd.DataFrame()

    def ref_cols(R, nivel):
        if R.empty:
            return R
        d = pd.DataFrame({"RESULTADO": R["CAT"], "REFERENCIA": R["REFERENCIA"], "DESCRIPCIÓN": R["DESCRIPCION"]})
        if nivel == "REFLOTE":
            d["LOTE"] = R["LOTE"]
            d["VENCE"] = pd.to_datetime(R["VENCE"])
            d["ESTADO VENC."] = R["ESTADO_VENC"]
        else:
            d["LOTES"] = R["LOTES"]
        d[ETQ] = R["ESPERADO"]
        d["CONTADO"] = R["CONTADO"]
        d["DIFERENCIA"] = R["DIFERENCIA"]
        if "GASTO" in R.columns and sha_de("gastos"):
            d["GASTOS (UND)"] = R["GASTO"]
            d["GASTO APLICADO"] = R["GASTO_APLICADO"]
            d["QUEDA TRAS GASTOS"] = R["DIF_TRAS_GASTO"]
            d["VALOR QUEDA TRAS GASTOS $"] = R["VALOR_TRAS_GASTO"].round(0)
            d["CASO · PACIENTE (CÉDULA) · FECHA · CLÍNICA"] = R["CASOS"]
        d["% CONTADO"] = (R["% CONTADO"] / 100).round(4)
        d["COSTO UNIT. $"] = R["COSTO_UNIT"].round(0)
        d["VALOR ESPERADO $"] = R["VALOR_ESPERADO"].round(0)
        d["VALOR DIFERENCIA $"] = R["VALOR_DIF"].round(0)
        d["CONCILIACIÓN"] = R["CONCILIACION"]
        d["OBSERVACIÓN"] = R["OBSERVACION"]
        d["REVISÓ"] = R["OBS_USUARIO"]
        d["FECHA REVISIÓN"] = R["OBS_FECHA"]
        if nivel == "REFLOTE":
            d["SERIALES"] = R["SERIALES"]
            d["GÓNDOLAS"] = R["GONDOLAS"]
        d["PAREJAS"] = R["PAREJAS"]
        orden = {"Faltante": 0, "Sobrante": 1, "Novedad": 2, "Pendiente": 3, "Cuadrado": 4}
        return d.assign(_o=d["RESULTADO"].map(orden)).sort_values(["_o", "REFERENCIA"]).drop(columns="_o")

    G = gastos_grupo(grupo) if sha_de("gastos") else pd.DataFrame()
    if not RR.empty:
        RR = con_gastos(RR, "REF", G)
        RL = con_gastos(RL, "REFLOTE", G)
    hRR, hRL = ref_cols(RR, "REF"), ref_cols(RL, "REFLOTE")
    dif = hRL[hRL["RESULTADO"].isin(["Faltante", "Sobrante", "Novedad"])] if not hRL.empty else hRL
    Ms = RL[RL["CAT"] != "Novedad"] if not RL.empty else RL
    esp = Ms["ESPERADO"].sum() if not Ms.empty else 0
    cob = np.minimum(Ms["CONTADO"], Ms["ESPERADO"]).sum() if not Ms.empty else 0
    falt = RL[RL["CAT"] == "Faltante"] if not RL.empty else RL
    sobr = RL[RL["CAT"] == "Sobrante"] if not RL.empty else RL
    n_cerr = int((sg["ESTADO"] == "✅ CERRADO").sum()) if not sg.empty else 0
    conc = int(((dif["CONCILIACIÓN"] != "Sin revisar") | (dif["OBSERVACIÓN"].astype(str).str.strip() != "")).sum()) if not dif.empty else 0
    kpis = [
        ("Avance del conteo", f"{pct(cob, esp):.1f}%", f"{fmt_num(cob)} de {fmt_num(esp)} und"),
        ("Unidades esperadas", fmt_num(esp), ETQ),
        ("Unidades contadas", fmt_num(RL["CONTADO"].sum() if not RL.empty else 0), "pistola + manual"),
        ("Seriales cerrados", f"{fmt_num(n_cerr)} / {fmt_num(len(sg))}", "según NAL"),
        ("Faltantes", fmt_num(-falt["DIFERENCIA"].sum() if not falt.empty else 0), fmt_cop(falt["VALOR_DIF"].sum() if not falt.empty else 0)),
        ("Sobrantes", fmt_num(sobr["DIFERENCIA"].sum() if not sobr.empty else 0), fmt_cop(sobr["VALOR_DIF"].sum() if not sobr.empty else 0)),
        ("Diferencia neta", fmt_cop(RL["VALOR_DIF"].sum() if not RL.empty else 0), f"{pct(abs(RL['VALOR_DIF'].sum()) if not RL.empty else 0, Ms['VALOR_ESPERADO'].sum() if not Ms.empty else 0):.2f}% del valor"),
        ("Diferencias conciliadas", f"{fmt_num(conc)} / {fmt_num(len(dif))}", "con estado y observación"),
    ]
    if sha_de("gastos") and not RL.empty:
        fl = RL[RL["CAT"] == "Faltante"]
        cubre = fl["GASTO_APLICADO"].sum()
        kpis.append(("Faltante cubierto por gastos", f"{fmt_num(cubre)} und",
                     f"{pct(cubre, -fl['DIFERENCIA'].sum()):.1f}% · queda {fmt_cop(fl['VALOR_TRAS_GASTO'].sum())}"))
    comp = pd.DataFrame()
    if not RL.empty:
        comp = RL.groupby("CAT").agg(LINEAS=("REFERENCIA", "count"), ESPERADO=("ESPERADO", "sum"),
                                     CONTADO=("CONTADO", "sum"), VALOR_DIF=("VALOR_DIF", "sum")).reindex(
            ["Cuadrado", "Faltante", "Sobrante", "Novedad", "Pendiente"]).dropna(how="all").fillna(0).reset_index()
        comp.columns = ["RESULTADO", "LÍNEAS", ETQ, "CONTADO", "VALOR DIFERENCIA $"]
    estado_conc = dif.groupby("CONCILIACIÓN").size().reset_index(name="DIFERENCIAS") if not dif.empty else pd.DataFrame()
    top = pd.DataFrame()
    if not hRL.empty:
        t = hRL[hRL["DIFERENCIA"] != 0].copy()
        t = t.reindex(t["VALOR DIFERENCIA $"].abs().sort_values(ascending=False).index).head(15)
        top = t[["REFERENCIA", "LOTE", "DESCRIPCIÓN", "DIFERENCIA", "VALOR DIFERENCIA $", "CONCILIACIÓN"]]
    meta = [("Grupo", nombre_g), ("Base de comparación", ETQ), ("Cliente", p["cliente"]),
            ("Responsable", p["responsable"] or "—"), ("Estado del conteo", "CERRADO" if conteo_cerrado() else "ABIERTO (lo no contado figura como pendiente)"),
            ("Criterio de bodegas", p["criterio"]), ("Valorización", p["base_valor"]),
            ("Archivos", f"NAL: {nombre_de('nal')} · Templete: {nombre_de('templete')} · Valref: {nombre_de('valref')}")]
    grafico = None
    if not comp.empty:
        col_map = {"Cuadrado": "#2A9D8F", "Faltante": "#D64545", "Sobrante": "#F2A541", "Novedad": "#8E6CCF", "Pendiente": "#AAB6C8"}
        grafico = (list(comp["RESULTADO"]), list(comp["LÍNEAS"]), [col_map[c] for c in comp["RESULTADO"]])
    L = lecturas_validas()
    lg = L[L["grupo"] == grupo] if not L.empty else L
    lect = pd.DataFrame()
    if not lg.empty:
        lect = pd.DataFrame({"FECHA / HORA": lg["ts"], "PAREJA": lg["pareja"], "MODO": lg["modo"], "ZONA": lg["zona"],
                             "GÓNDOLA": lg["gondola"], "NIVEL": lg["nivel"], "SERIAL": lg["serial"],
                             "REFERENCIA": lg["referencia"], "DESCRIPCIÓN": lg["descripcion"], "LOTE": lg["lote"],
                             "VENCE": pd.to_datetime(lg["VENCE_L"]), "CANTIDAD": lg["cantidad"],
                             "OBSERVACIÓN": lg["observacion"], "LECTURA CRUDA": lg["codigo_leido"]}).sort_values("FECHA / HORA")
    ser = pd.DataFrame()
    if not sg.empty:
        ser = pd.DataFrame({"ESTADO": sg["ESTADO"], "SERIAL": sg["SERIAL"], "SET": sg["SET"], "BODEGA": sg["BODEGA_NOM"],
                            "ORIGEN": sg["ORIGEN_BOD"], "UNIDADES NAL": sg["UNIDADES"], "CONTADO": sg["CONTADO"],
                            "DIFERENCIA": sg["CONTADO"] - sg["UNIDADES"], "PAREJAS": sg["PAREJAS"],
                            "CERRADO POR": sg.get("CERRADO_POR", ""), "ÚLTIMA LECTURA": sg["ULTIMA"]})
    venc = hRL[hRL["ESTADO VENC."].isin(["VENCIDO", "PRÓXIMO A VENCER"])].sort_values("VENCE") if not hRL.empty else hRL
    fx = ctx["UV"]["excl"]
    fuera = fx[fx["GRUPO"] == grupo] if not fx.empty else fx
    Hc = leer_correcciones()
    hojas = {
        "Cruce por Referencia": hRR,
        "Cruce Ref-Lote": hRL,
        "Diferencias a Conciliar": dif,
        **({"Gastos x Referencia": gastos_hoja(hRR), "Gastos x Ref-Lote": gastos_hoja(hRL),
            "Detalle Gastos Pacientes": detalle_gastos_hoja(G, RL)} if sha_de("gastos") else {}),
        "Seriales": ser,
        "Vencimientos": venc,
        "Fuera de Alcance": fuera,
        "Lecturas": lect,
        "Historial Correcciones": Hc.drop(columns=["id"], errors="ignore") if not Hc.empty else Hc,
    }
    ctrl = []
    for R_, nivel_ in ((RR, "REF"), (RL, "REFLOTE")):
        if R_ is not None and not R_.empty:
            ctrl.append(pd.DataFrame({"HOJA_NIVEL": nivel_, "REF": R_["REFERENCIA"].astype(str),
                                      "LOTE": R_["LOTE"].astype(str) if "LOTE" in R_.columns else "",
                                      "ID": R_["ID_OBS"], "OBS": R_["OBSERVACION"], "CONC": R_["CONCILIACION"]}))
    hojas["_control"] = pd.concat(ctrl, ignore_index=True) if ctrl else pd.DataFrame(columns=["ID", "OBS", "CONC"])
    portada = dict(meta=meta, kpis=kpis, grafico=grafico,
                   tablas=[("Resultado del cruce", comp), ("Estado de la conciliación", estado_conc),
                           ("Top 15 diferencias por valor", top)])
    titulo = f"CONCILIACIÓN DE INVENTARIO · {nombre_g.upper()}"
    return excel_corporativo(hojas, titulo, f"{p['cliente']} · corte {ahora():%d/%m/%Y %H:%M}", portada)



# =============================================================================
# GASTOS / CONSUMOS (archivo Con_Equipo): justifican faltantes con caso y paciente
# =============================================================================

@st.cache_data(show_spinner="Leyendo gastos (consumos de cirugía)…")
def leer_gastos(data: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(data), dtype=str)
    else:
        df = leer_csv_flexible(data)
    df.columns = [str(c).strip() for c in df.columns]
    def c(*n):
        return find_col(df, *n, parcial=False)
    c_cor, c_ref, c_nom = c("COD. CORTO", "COD CORTO"), c("REFERENCIA"), c("NOMBRE")
    c_can, c_lot, c_fec = c("CAN-CONSUM", "CANTIDAD"), c("LOTE"), c("FEC-CONS", "FECHA CONSUMO")
    c_cas, c_ced, c_pac = c("NO. CASO", "NO CASO", "CASO"), c("CED-PACIENTE", "CEDULA PACIENTE"), c("NOMBRE PACIENTE", "PACIENTE")
    c_cli, c_doc, c_con = c("NOMBRE CLIENTE", "CLIENTE"), c("DOCTOR"), c("CONSUMO")
    c_rem, c_bod, c_ser = c("REMISION"), c("BODEGA SALIDA"), c("SERIAL")
    c_pro, c_proc, c_cir = c("PROVEEDOR"), c("PROCEDIMIENTO"), c("CIRUGIA")
    if not c_lot or not (c_cor or c_ref):
        raise ValueError("El archivo de gastos debe tener columnas de referencia (COD. CORTO) y LOTE.")
    def txt(col):
        return df[col].astype("string").fillna("").str.strip().astype(str) if col else pd.Series("", index=df.index)
    ref = limpiar_codigo(df[c_cor]) if c_cor else pd.Series("", index=df.index)
    if c_ref:
        alt = limpiar_codigo(df[c_ref]).str.split("-").str[-1]
        ref = ref.where(ref != "", alt)
    out = pd.DataFrame({
        "REFERENCIA": ref, "DESCRIPCION": txt(c_nom), "LOTE_ORIG": txt(c_lot), "LOTE": limpiar_lote(df[c_lot]),
        "CANT": to_num(df[c_can]).fillna(1) if c_can else 1.0,
        "FECHA": parse_fecha(df[c_fec]) if c_fec else pd.NaT,
        "CASO": txt(c_cas), "CEDULA": txt(c_ced), "PACIENTE": txt(c_pac), "CLINICA": txt(c_cli),
        "DOCTOR": txt(c_doc), "CONSUMO": txt(c_con), "REMISION": txt(c_rem), "BODEGA_SALIDA": txt(c_bod),
        "SERIAL": txt(c_ser), "PROVEEDOR": txt(c_pro), "PROCEDIMIENTO": txt(c_proc), "CIRUGIA": txt(c_cir),
    })
    out = out[out["REFERENCIA"] != ""].copy()
    out["K_REF"] = clave(out["REFERENCIA"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True)
    bod = pd.to_numeric(out["BODEGA_SALIDA"].str.extract(r"^\s*(\d+)")[0], errors="coerce")
    out["GRUPO"] = np.where(bod.isin(BODEGAS_SERENA), "SERENA",
                            np.where(out["PROVEEDOR"].str.upper().str.contains("SMITH"), "SMITH", ""))
    out["CASO_TXT"] = (np.where(out["CASO"] != "", "Caso " + out["CASO"], "Consumo " + out["CONSUMO"]) + " · "
                       + out["PACIENTE"] + " (CC " + out["CEDULA"] + ") · "
                       + out["FECHA"].dt.strftime("%d/%m/%Y").fillna("") + " · " + out["CLINICA"].str[:30])
    return out[out["GRUPO"] != ""].reset_index(drop=True)


def gastos_grupo(grupo: str) -> pd.DataFrame:
    sha = sha_de("gastos")
    if not sha:
        return pd.DataFrame()
    G = leer_gastos(bytes_maestro("gastos", sha), nombre_de("gastos") or "gastos.csv")
    G = G[G["GRUPO"] == grupo]
    desde = cfg("gastos_desde", "")
    if desde:
        G = G[G["FECHA"].isna() | (G["FECHA"] >= pd.Timestamp(desde))]
    return G


def con_gastos(R: pd.DataFrame, nivel: str, G: pd.DataFrame) -> pd.DataFrame:
    """Agrega a un cruce las unidades consumidas (gastos) y la diferencia que queda después de aplicarlas."""
    R = R.copy()
    llaves = ["K_REF"] if nivel == "REF" else ["K_REF", "K_LOTE"]
    if G is None or G.empty:
        R["GASTO"], R["N_GASTOS"], R["CASOS"] = 0.0, 0, ""
    else:
        Gg = G.groupby(llaves, as_index=False).agg(
            GASTO=("CANT", "sum"), N_GASTOS=("CANT", "size"),
            CASOS=("CASO_TXT", lambda x: " | ".join(list(dict.fromkeys(x))[:4]) + (" | …" if len(set(x)) > 4 else "")))
        R = R.merge(Gg, on=llaves, how="left")
        R["GASTO"] = R["GASTO"].fillna(0)
        R["N_GASTOS"] = R["N_GASTOS"].fillna(0).astype(int)
        R["CASOS"] = R["CASOS"].fillna("")
    falt = (-R["DIFERENCIA"]).clip(lower=0)
    R["GASTO_APLICADO"] = np.minimum(R["GASTO"], falt)
    R["DIF_TRAS_GASTO"] = R["DIFERENCIA"] + R["GASTO_APLICADO"]
    R["VALOR_TRAS_GASTO"] = R["DIF_TRAS_GASTO"] * R["COSTO_UNIT"]
    return R


def vista_gastos(ctx, grupo: str, RR: pd.DataFrame, RL: pd.DataFrame, buscar: str):
    if not sha_de("gastos"):
        alerta("ℹ️ Cargue el archivo de <b>gastos / consumos</b> (Con_Equipo) en <b>⚙️ Maestros</b> para cruzarlo con los faltantes.", "azul")
        return
    G = gastos_grupo(grupo)
    c1, c2, c3 = st.columns([2.2, 1.4, 1.4])
    modo = c1.radio("Cruzar faltantes con gastos por", ["Referencia y cantidades", "Referencia + lote"], horizontal=True,
                    key=f"gmodo_{grupo}")
    actual = cfg("gastos_desde", "")
    d = c2.date_input("Considerar gastos desde", value=pd.Timestamp(actual).date() if actual else None,
                      format="DD/MM/YYYY", key=f"gdesde_{grupo}")
    nuevo = d.isoformat() if d else ""
    if nuevo != actual:
        cfg_set("gastos_desde", nuevo)
        st.rerun()
    c3.metric("Gastos en el período", fmt_num(G["CANT"].sum() if not G.empty else 0), f"{fmt_num(len(G))} registros")
    nivel = "REF" if modo.startswith("Referencia y") else "REFLOTE"
    base = con_observaciones(RR if nivel == "REF" else RL, grupo, nivel)
    X = con_gastos(base, nivel, G)
    F = X[X["CAT"] == "Faltante"].copy()
    if buscar.strip():
        b_ = buscar.strip().upper()
        F = F[F["REFERENCIA"].str.upper().str.contains(b_, regex=False) | F["CASOS"].str.upper().str.contains(b_, regex=False)
              | (F["LOTE"].astype(str).str.upper().str.contains(b_, regex=False) if "LOTE" in F.columns else False)]
    tot_f = -F["DIFERENCIA"].sum()
    cub = F["GASTO_APLICADO"].sum()
    k = st.columns(4)
    kpi(k[0], "Faltante", fmt_num(tot_f), fmt_cop(F["VALOR_DIF"].sum()), C["rojo"])
    kpi(k[1], "Cubierto por gastos", fmt_num(cub), f"{pct(cub, tot_f):.1f}% del faltante", C["verde"], pct(cub, tot_f))
    kpi(k[2], "Faltante tras gastos", fmt_num(-F["DIF_TRAS_GASTO"].sum()), fmt_cop(F["VALOR_TRAS_GASTO"].sum()), C["ambar"])
    kpi(k[3], "Líneas 100 % cubiertas", fmt_num(int(((F["DIF_TRAS_GASTO"] == 0) & (F["GASTO_APLICADO"] > 0)).sum())),
        f"de {fmt_num(len(F))} faltantes", C["navy"])
    st.write("")
    cols = {"REFERENCIA": "REFERENCIA"}
    if nivel == "REFLOTE":
        cols["LOTE"] = "LOTE"
    cols.update({"DESCRIPCION": "DESCRIPCIÓN", "DIFERENCIA": "FALTANTE", "GASTO": "GASTOS (UND)",
                 "GASTO_APLICADO": "GASTO APLICADO", "DIF_TRAS_GASTO": "QUEDA", "CASOS": "CASO · PACIENTE (CÉDULA) · FECHA · CLÍNICA",
                 "CONCILIACION": "CONCILIACIÓN", "OBSERVACION": "OBSERVACIÓN"})
    Fv = F.sort_values(["GASTO_APLICADO", "REFERENCIA"], ascending=[False, True])
    st.dataframe(Fv[list(cols)].rename(columns=cols), hide_index=True, height=360,
                 column_config={"FALTANTE": st.column_config.NumberColumn(format="%d"),
                                "GASTOS (UND)": st.column_config.NumberColumn(format="%d"),
                                "GASTO APLICADO": st.column_config.NumberColumn(format="%d"),
                                "QUEDA": st.column_config.NumberColumn(format="%d"),
                                "CASO · PACIENTE (CÉDULA) · FECHA · CLÍNICA": st.column_config.TextColumn(width="large")})
    # Detalle de pacientes
    llaves = ["K_REF"] if nivel == "REF" else ["K_REF", "K_LOTE"]
    det = G.merge(F[llaves].drop_duplicates(), on=llaves, how="inner") if not G.empty and not F.empty else pd.DataFrame()
    with st.expander(f"🩺 Detalle de gastos (caso, paciente y cédula) que explican faltantes · {fmt_num(len(det))} registros"):
        if det.empty:
            st.info("No hay gastos que coincidan con los faltantes en el período elegido.")
        else:
            st.dataframe(det[["FECHA", "CASO", "PACIENTE", "CEDULA", "REFERENCIA", "LOTE_ORIG", "CANT", "CLINICA", "DOCTOR",
                              "CONSUMO", "REMISION", "BODEGA_SALIDA", "PROCEDIMIENTO"]].rename(columns={
                "CASO": "N° CASO", "CEDULA": "CÉDULA", "LOTE_ORIG": "LOTE", "CANT": "CANTIDAD", "CLINICA": "CLÍNICA",
                "BODEGA_SALIDA": "BODEGA SALIDA"}).sort_values("FECHA"), hide_index=True, height=300,
                column_config={"FECHA": st.column_config.DateColumn(format="DD/MM/YYYY")})
    # Aplicar a la conciliación
    aplicables = F[(F["GASTO_APLICADO"] > 0) & (F["CONCILIACION"] == "Sin revisar") & (F["OBSERVACION"].str.strip() == "")]
    st.caption(f"{fmt_num(len(aplicables))} faltantes con gasto aún sin conciliar ({modo.lower()}).")
    if st.button(f"✅ Aplicar gastos a la conciliación ({fmt_num(len(aplicables))})", disabled=aplicables.empty,
                 key=f"aplicar_g_{grupo}_{nivel}", type="primary"):
        cambios = []
        for _, r in aplicables.iterrows():
            queda = int(-r["DIF_TRAS_GASTO"])
            obs = f"Gasto {int(r['GASTO_APLICADO'])} und: {r['CASOS']}"
            if queda > 0:
                obs += f" · Quedan {queda} und sin justificar"
            cambios.append(dict(grupo=grupo, nivel=nivel, k_ref=r["K_REF"], k_lote=r["K_LOTE"] if nivel == "REFLOTE" else "",
                                observacion=obs[:500],
                                conciliacion="Justificada con gasto" if queda == 0 else "En investigación"))
        guardar_observaciones(cambios, "Administrador (gastos)")
        st.success(f"{len(cambios)} diferencias actualizadas con los gastos. Puede revisarlas en la vista de cruce.")
        st.rerun()


# =============================================================================
# IMPORTAR EL EXCEL DE CONCILIACIÓN TRABAJADO
# =============================================================================

def _normaliza_conc(v) -> str:
    t = str(v or "").strip()
    if not t or t.lower() == "nan":
        return "Sin revisar"
    for o in OPC_CONCILIACION:
        if norm(o) == norm(t):
            return o
    return "En investigación"


def importar_excel_conciliacion(data: bytes, grupo: str, nombre_archivo: str) -> dict:
    """Lee CONCILIACIÓN y OBSERVACIÓN del Excel descargado (y editado) y actualiza solo lo que cambió."""
    xls = pd.ExcelFile(io.BytesIO(data))
    O = leer_observaciones()
    actuales = {r["id"]: (str(r["observacion"]), str(r["conciliacion"] or "Sin revisar")) for _, r in O.iterrows()} if not O.empty else {}
    # Valores tal como se descargaron (hoja oculta): solo se toma lo que el usuario cambió en el Excel
    exportado = None
    if "_control" in xls.sheet_names:
        ctl = pd.read_excel(xls, sheet_name="_control", dtype=str).fillna("")
        exportado = {r["ID"]: (str(r["OBS"]).strip(), str(r["CONC"] or "Sin revisar")) for _, r in ctl.iterrows()}
        g_ctl = {i.split("|")[0] for i in exportado if "|" in i}
        if g_ctl and grupo not in g_ctl:
            raise ValueError(f"Este Excel es de {', '.join(sorted(g_ctl))}; súbalo en esa sección.")
    propuestas, leidas, por_hoja = {}, 0, {}
    # La hoja de diferencias se procesa al final: si se editó la misma fila en dos hojas, gana la de diferencias
    for hoja, nivel in [("Cruce por Referencia", "REF"), ("Cruce Ref-Lote", "REFLOTE"), ("Diferencias a Conciliar", "REFLOTE")]:
        if hoja not in xls.sheet_names:
            continue
        raw = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=object)
        h = detectar_encabezado(raw, {"REFERENCIA"}, {"CONCILIACION", "OBSERVACION"})
        if h is None:
            continue
        df = raw.iloc[h + 1:].copy()
        df.columns = unicos(raw.iloc[h].tolist())
        c_ref = find_col(df, "REFERENCIA", parcial=False)
        c_lot = find_col(df, "LOTE", parcial=False)
        c_con = find_col(df, "CONCILIACIÓN", "CONCILIACION", parcial=False)
        c_obs = find_col(df, "OBSERVACIÓN", "OBSERVACION", parcial=False)
        if not c_ref or not (c_con or c_obs):
            continue
        n = 0
        for _, r in df.iterrows():
            ref = r.get(c_ref)
            if ref is None or (not isinstance(ref, str) and pd.isna(ref)) or str(ref).upper().startswith("TOTAL"):
                continue
            kr = clave(limpiar_codigo(pd.Series([str(ref)]))).iloc[0]
            kl = ""
            if nivel == "REFLOTE":
                lv = r.get(c_lot) if c_lot else ""
                kl = clave(limpiar_lote(pd.Series(["" if lv is None or (not isinstance(lv, str) and pd.isna(lv)) else str(lv)])), es_lote=True).iloc[0]
            obs = r.get(c_obs) if c_obs else ""
            obs = "" if obs is None or (not isinstance(obs, str) and pd.isna(obs)) else str(obs).strip()
            conc = _normaliza_conc(r.get(c_con) if c_con else "")
            oid = f"{grupo}|{nivel}|{kr}|{kl}"[:200]
            leidas += 1
            n += 1
            if exportado is not None:
                base = exportado.get(oid, ("", "Sin revisar"))
            else:
                base = actuales.get(oid, ("", "Sin revisar"))
            if (obs, conc) != (base[0].strip(), base[1] or "Sin revisar"):
                ahora_db = actuales.get(oid, ("", "Sin revisar"))
                if (obs, conc) != (ahora_db[0].strip(), ahora_db[1] or "Sin revisar"):
                    propuestas[oid] = dict(grupo=grupo, nivel=nivel, k_ref=kr, k_lote=kl, observacion=obs, conciliacion=conc)
        por_hoja[hoja] = n
    if propuestas:
        guardar_observaciones(list(propuestas.values()), f"Excel: {nombre_archivo}"[:80])
    return dict(leidas=leidas, actualizadas=len(propuestas), hojas=por_hoja)


def panel_importar_excel(grupo: str):
    with st.expander("📤 Subir el Excel de conciliación trabajado (actualiza observaciones y estados)"):
        st.caption("Descargue el Excel, escriba en las columnas **CONCILIACIÓN** y **OBSERVACIÓN** "
                   "(hojas *Cruce por Referencia*, *Cruce Ref-Lote* o *Diferencias a Conciliar*), guárdelo y súbalo aquí. "
                   "Solo se actualiza lo que usted cambió; las cantidades se recalculan con el conteo actual.")
        f = st.file_uploader("Excel de conciliación (.xlsx)", type=["xlsx"], key=f"imp_{grupo}")
        if f is not None and st.button("Importar cambios del Excel", type="primary", key=f"btn_imp_{grupo}"):
            try:
                res = importar_excel_conciliacion(f.getvalue(), grupo, f.name)
                st.session_state[f"imp_res_{grupo}"] = res
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")
        res = st.session_state.pop(f"imp_res_{grupo}", None)
        if res:
            st.success(f"✔ Se leyeron {fmt_num(res['leidas'])} filas y se actualizaron {fmt_num(res['actualizadas'])} "
                       f"observaciones/estados. Hojas: " + ", ".join(f"{k} ({v})" for k, v in res["hojas"].items()))



def gastos_hoja(h: pd.DataFrame) -> pd.DataFrame:
    if h is None or h.empty or "GASTOS (UND)" not in h.columns:
        return pd.DataFrame()
    return h[(h["RESULTADO"] == "Faltante")].sort_values(["GASTO APLICADO", "REFERENCIA"], ascending=[False, True])


def detalle_gastos_hoja(G: pd.DataFrame, RL: pd.DataFrame) -> pd.DataFrame:
    if G is None or G.empty or RL is None or RL.empty:
        return pd.DataFrame()
    falt = RL[RL["CAT"] == "Faltante"]
    d = G[G["K_REF"].isin(set(falt["K_REF"]))].copy()
    pares = set(zip(falt["K_REF"], falt["K_LOTE"]))
    d["COINCIDE LOTE"] = ["Sí" if (a, b) in pares else "No (solo referencia)" for a, b in zip(d["K_REF"], d["K_LOTE"])]
    return pd.DataFrame({"FECHA": d["FECHA"], "N° CASO": d["CASO"], "PACIENTE": d["PACIENTE"], "CÉDULA": d["CEDULA"],
                         "REFERENCIA": d["REFERENCIA"], "DESCRIPCIÓN": d["DESCRIPCION"], "LOTE": d["LOTE_ORIG"],
                         "COINCIDE LOTE": d["COINCIDE LOTE"], "CANTIDAD": d["CANT"], "CLÍNICA": d["CLINICA"],
                         "DOCTOR": d["DOCTOR"], "CONSUMO": d["CONSUMO"], "REMISIÓN": d["REMISION"],
                         "BODEGA SALIDA": d["BODEGA_SALIDA"], "PROCEDIMIENTO": d["PROCEDIMIENTO"]}).sort_values("FECHA")


def excel_grupo(ctx, grupo, M, Ms, Se, L, T) -> dict:
    p = ctx["p"]
    sis = Ms["SISTEMA"].sum()
    sg = Se[Se["GRUPO"] == grupo] if not Se.empty else Se
    res = pd.DataFrame([
        ("Fecha de generación", ahora().strftime("%d/%m/%Y %H:%M")), ("Cliente", p["cliente"]), ("Responsable", p["responsable"]),
        ("Bodegas", ", ".join(map(str, BODEGAS_SMITH if grupo == "SMITH" else BODEGAS_SERENA))
         + (" + seriales de las bodegas 02, 10, 20, 27 y 33 (refs del templete con lote sin * / **)"
            if grupo == "SMITH" and p["incluir_otras"] else "")),
        ("Criterio de bodega", p["criterio"]), ("Archivo NAL", nombre_de("nal")), ("Archivo Valref", nombre_de("valref")),
        (f"Unidades esperadas ({etq_esperado(ctx, grupo)})", sis), ("Unidades contadas", M["CONTADO"].sum()),
        ("Avance (cobertura) %", round(pct(np.minimum(Ms["CONTADO"], Ms["SISTEMA"]).sum(), sis), 2)),
        ("Seriales totales", len(sg)), ("Seriales cerrados", int((sg["ESTADO"] == "✅ CERRADO").sum()) if not sg.empty else 0),
        ("Seriales pendientes", int((sg["ESTADO"] == "⏳ PENDIENTE").sum()) if not sg.empty else 0),
        ("Unidades faltantes", -Ms.loc[Ms["DIFERENCIA"] < 0, "DIFERENCIA"].sum()),
        ("Unidades sobrantes / novedades", M.loc[M["DIFERENCIA"] > 0, "DIFERENCIA"].sum()),
        ("Valor en sistema $", Ms["VALOR_SISTEMA"].sum()), ("Valor faltante $", Ms.loc[Ms["DIFERENCIA"] < 0, "VALOR_DIF"].sum()),
        ("Valor sobrante $", M.loc[M["DIFERENCIA"] > 0, "VALOR_DIF"].sum()), ("Diferencia neta $", M["VALOR_DIF"].sum()),
        ("Lotes vencidos", int((Ms["ESTADO_VENC"] == "VENCIDO").sum())),
        ("Registros fuera de alcance (no se cuentan)",
         int((ctx["UV"]["excl"]["GRUPO"] == grupo).sum()) if not ctx["UV"]["excl"].empty else 0),
        ("Alcance", "Solo implantes del templete Smith (instrumental excluido)" if grupo == "SMITH" and p["solo_implantes"]
         else ("Referencias del templete Serena del Mar" if grupo == "SERENA" and ctx["UV"]["info"].get("serena_tpl")
               else "Todo el NAL del grupo")),
    ], columns=["INDICADOR", "VALOR"])
    res["VALOR"] = res["VALOR"].astype(str)
    sg_x = sg.assign(DIFERENCIA=sg["CONTADO"] - sg["UNIDADES"]) if not sg.empty else sg
    lg = L[L["grupo"] == grupo].drop(columns=["K_REF", "K_LOTE", "SERIAL", "VENCE_L"], errors="ignore") if not L.empty else L
    h = {
        "Resumen": res,
        "Sistema_vs_Conteo" if grupo != "SMITH" else "Templete_vs_Conteo_PhysInv": para_excel(
            M.rename(columns={"SISTEMA": etq_esperado(ctx, grupo), "NAL": "NAL (INFORMATIVO)"})),
        "Totales_Referencia": para_excel(totales_ref(Ms)),
        "Seriales": para_excel(sg_x),
        "Faltantes": para_excel(Ms[Ms["DIFERENCIA"] < 0]),
        "Sobrantes_y_Novedades": para_excel(M[(M["DIFERENCIA"] > 0) | (M["MANUAL"] > 0)]),
        "Stock_Seguridad": para_excel(M[M["TIPO"] == "STOCK"]),
        "Vencimientos": para_excel(Ms[Ms["ESTADO_VENC"].isin(["VENCIDO", "PRÓXIMO A VENCER"])].sort_values("VENCE")),
        "Lecturas": lg,
    }
    if grupo == "SERENA" and not ctx["UV"]["excl"].empty:
        fx = ctx["UV"]["excl"]
        h["Fuera_de_Alcance"] = fx[fx["GRUPO"] == "SERENA"]
    if grupo == "SMITH":
        if T is not None and not ctx["sha_tpl"]:
            h["Templete_vs_Conteo"] = para_excel(templete_vs_conteo(T, L, ctx["U"], p["base_valor"], ctx["lotes"]))
        fx = ctx["UV"]["excl"]
        h["Fuera_de_Alcance"] = fx[fx["GRUPO"] == "SMITH"] if not fx.empty else fx
        h["Saldos_Negativos_NAL"] = ctx["UV"]["neg"]
        h["Conciliacion_Com_Lot"] = para_excel(ctx["UV"]["conc"]) if not ctx["UV"]["conc"].empty else pd.DataFrame()
    return h


def admin_dashboard(ctx):
    U, S, p = ctx["U"], ctx["S"], ctx["p"]
    L = lecturas_validas()
    if U.empty and L.empty:
        alerta("ℹ️ El tablero se llena cuando se cargan los maestros y empiezan las lecturas.", "azul")
        return
    Se = estado_seriales(S, L) if not S.empty else S
    res = {}
    for g in ["SMITH", "SERENA"]:
        M, _ = obtener_cruce(g)
        M = M.drop(columns=["CATEGORIA"], errors="ignore")
        if M.empty:
            res[g] = dict(sis=0, con=0, cob=0, falt=0, sobr=0, vf=0, vs=0, vsis=0, M=M, exa=0, n=0, pend=0)
            continue
        nol = M["ESTADO"].str.startswith("🆕") | M["ESTADO"].str.startswith("⚠️")
        Ms = M[~nol]
        Mf = Ms[(Ms["DIFERENCIA"] < 0) & ~Ms["ESTADO"].str.startswith("⏳")]
        res[g] = dict(sis=Ms["SISTEMA"].sum(), con=M["CONTADO"].sum(), cob=np.minimum(Ms["CONTADO"], Ms["SISTEMA"]).sum(),
                      falt=-Mf["DIFERENCIA"].sum(), sobr=M.loc[M["DIFERENCIA"] > 0, "DIFERENCIA"].sum(),
                      vf=Mf["VALOR_DIF"].sum(), vs=M.loc[M["DIFERENCIA"] > 0, "VALOR_DIF"].sum(),
                      vsis=Ms["VALOR_SISTEMA"].sum(), M=M, exa=int((Ms["DIFERENCIA"] == 0).sum()), n=len(Ms),
                      pend=Ms.loc[Ms["ESTADO"].str.startswith("⏳"), "SISTEMA"].sum())
    sm, se = res["SMITH"], res["SERENA"]
    tot = {k: sm[k] + se[k] for k in ["sis", "con", "cob", "falt", "sobr", "vf", "vs", "vsis", "exa", "n", "pend"]}
    st.markdown(f"#### Resumen ejecutivo · {p['cliente']} · corte {ahora():%d/%m/%Y %H:%M}")
    r1 = st.columns(4)
    av = pct(tot["cob"], tot["sis"])
    kpi(r1[0], "Avance global", f"{av:.1f}%", f"{fmt_num(tot['cob'])} de {fmt_num(tot['sis'])} und", C["teal"], av)
    kpi(r1[1], "Smith & Nephew", f"{pct(sm['cob'], sm['sis']):.1f}%", "bod. 58·59·81·82·83·84 + seriales Valref", C["navy"], pct(sm["cob"], sm["sis"]))
    kpi(r1[2], "Serena del Mar", f"{pct(se['cob'], se['sis']):.1f}%", "bodegas 66 · 67", C["azul"], pct(se["cob"], se["sis"]))
    n_ser = len(Se) if not Se.empty else 0
    n_cer = int((Se["ESTADO"] == "✅ CERRADO").sum()) if n_ser else 0
    kpi(r1[3], "Seriales cerrados", f"{pct(n_cer, n_ser):.1f}%", f"{fmt_num(n_cer)} de {fmt_num(n_ser)}", C["verde"], pct(n_cer, n_ser))
    st.write("")
    r2 = st.columns(4)
    kpi(r2[0], "Valor en sistema", fmt_cop(tot["vsis"]), p["base_valor"], C["navy"])
    kpi(r2[1], "Valor faltante", fmt_cop(tot["vf"]), f"{fmt_num(tot['falt'])} und · sin contar {fmt_num(tot['pend'])} und en seriales pendientes", C["rojo"])
    kpi(r2[2], "Valor sobrante / novedades", fmt_cop(tot["vs"]), f"{fmt_num(tot['sobr'])} und", C["ambar"])
    neto = tot["vf"] + tot["vs"]
    kpi(r2[3], "Diferencia neta", fmt_cop(neto), f"Exactitud por línea: {pct(tot['exa'], tot['n']):.1f}%",
        C["rojo"] if neto < 0 else C["verde"])
    st.write("")
    g1, g2 = st.columns([1, 1.6])
    with g1:
        fig = go.Figure(go.Pie(labels=["Contado", "Pendiente"], values=[tot["cob"], max(tot["sis"] - tot["cob"], 0)], hole=.68,
                               marker=dict(colors=[C["teal"], "#DDE3EC"]), sort=False, textinfo="percent"))
        fig.add_annotation(text=f"<b>{av:.1f}%</b><br>avance", showarrow=False, font=dict(size=22, color=C["navy"]))
        st.plotly_chart(layout_fig(fig, 330, "Ítems contados vs pendientes"), key="d_donut")
    with g2:
        fig = go.Figure()
        for nm, k_, colr in [("Sistema", "sis", C["gris"]), ("Contado", "con", C["teal"]), ("Serial pendiente", "pend", "#C9D3E0"),
                             ("Faltante", "falt", C["rojo"]), ("Sobrante", "sobr", C["ambar"])]:
            fig.add_bar(name=nm, x=["Smith & Nephew", "Serena del Mar"], y=[sm[k_], se[k_]], marker_color=colr,
                        text=[fmt_num(sm[k_]), fmt_num(se[k_])], textposition="outside")
        fig.update_layout(barmode="group")
        st.plotly_chart(layout_fig(fig, 330, "Unidades por sección"), key="d_bar")
    g3, g4 = st.columns([1.6, 1])
    with g3:
        top = pd.concat([sm["M"].assign(SEC="Smith"), se["M"].assign(SEC="Serena")]) if not (sm["M"].empty and se["M"].empty) else pd.DataFrame()
        top = top[top["VALOR_DIF"] != 0] if not top.empty else top
        if top.empty:
            st.info("Sin diferencias valorizadas todavía.")
        else:
            top = top.groupby(["SEC", "REFERENCIA"], as_index=False).agg(DES=("DESCRIPCION", "first"), V=("VALOR_DIF", "sum"))
            top = top.reindex(top["V"].abs().sort_values(ascending=False).index).head(12).iloc[::-1]
            fig = go.Figure(go.Bar(x=top["V"], y=top["REFERENCIA"] + " · " + top["DES"].str[:26], orientation="h",
                                   marker_color=np.where(top["V"] < 0, C["rojo"], C["ambar"]),
                                   text=[fmt_cop(v) for v in top["V"]], textposition="auto"))
            st.plotly_chart(layout_fig(fig, 420, "Top 12 diferencias valorizadas"), key="d_top")
    with g4:
        if n_ser:
            cnt = Se.groupby(["GRUPO", "ESTADO"]).size().reset_index(name="N")
            fig = px.bar(cnt, x="GRUPO", y="N", color="ESTADO", text="N",
                         color_discrete_map={"⏳ PENDIENTE": C["rojo"], "🔄 EN CONTEO": C["ambar"], "✅ CERRADO": C["verde"]})
            st.plotly_chart(layout_fig(fig, 420, "Estado de seriales"), key="d_ser")
    traz, det = trazabilidad()
    if not traz.empty:
        g5, g6 = st.columns(2)
        with g5:
            fig = px.bar(traz.sort_values("UNIDADES"), x="UNIDADES", y="PAREJA", orientation="h", text="UNIDADES",
                         color_discrete_sequence=[C["navy"]])
            st.plotly_chart(layout_fig(fig, 320, "Productividad por pareja"), key="d_par")
        with g6:
            d = det[det["anulada"] == 0].copy()
            d["HORA"] = pd.to_datetime(d["ts"], errors="coerce").dt.floor("h")
            d = d.dropna(subset=["HORA"]).groupby("HORA", as_index=False)["cantidad"].sum()
            if not d.empty:
                d["ACUM"] = d["cantidad"].cumsum()
                fig = go.Figure(go.Scatter(x=d["HORA"], y=d["ACUM"], mode="lines+markers", fill="tozeroy",
                                           line=dict(color=C["teal"], width=3)))
                st.plotly_chart(layout_fig(fig, 320, "Ritmo del conteo (unidades acumuladas)"), key="d_ritmo")
    tabla = pd.DataFrame([{"SECCIÓN": n, "UND. SISTEMA": d_["sis"], "UND. CONTADAS": d_["con"],
                           "AVANCE %": round(pct(d_["cob"], d_["sis"]), 1), "FALTANTES": d_["falt"], "SOBRANTES": d_["sobr"],
                           "VALOR SISTEMA": d_["vsis"], "VALOR FALTANTE": d_["vf"], "VALOR SOBRANTE": d_["vs"],
                           "DIF. NETA": d_["vf"] + d_["vs"]}
                          for n, d_ in [("Smith & Nephew", sm), ("Serena del Mar", se), ("TOTAL", tot)]])
    seccion("📌 Tabla resumen para la gerencia")
    st.dataframe(tabla, hide_index=True)
    st.download_button("⬇️ Resumen gerencial (.xlsx)", data=lambda: a_excel({"Resumen_Gerencial": tabla}, "RESUMEN GERENCIAL DEL INVENTARIO",
                                                                    p["cliente"]),
                       file_name=f"Resumen_Gerencial_{ahora():%Y%m%d_%H%M}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =============================================================================
# INGRESO Y NAVEGACIÓN
# =============================================================================

def pantalla_login():
    st.markdown("<style>section[data-testid='stSidebar']{display:none;}</style>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.5, 1])
    with centro:
        st.markdown(logo_html(), unsafe_allow_html=True)
        st.markdown('<div class="banner" style="text-align:center"><h1>Control de Inventario Físico</h1>'
                    '<p>Smith &amp; Nephew · Tecnitrauma</p></div>', unsafe_allow_html=True)
        if st.session_state.get("intentos", 0) >= 8:
            st.error("Demasiados intentos fallidos. Cierre y vuelva a abrir el navegador.")
            return
        t1, t2 = st.tabs(["👥 Pareja de conteo", "🔐 Administrador"])
        with t1:
            P = leer_parejas()
            act = P[P["estado"] == "Activa"] if not P.empty else P
            if act.empty:
                st.info("El administrador aún no ha creado parejas de conteo.")
            else:
                with st.form("login_par"):
                    nom = st.selectbox("Su pareja", list(act["nombre"]))
                    pin = st.text_input("PIN de 4 dígitos", type="password", max_chars=4)
                    if st.form_submit_button("Ingresar a contar", type="primary", width="stretch"):
                        r = act[act["nombre"] == nom].iloc[0]
                        if pin.strip() and pin.strip() == str(r["pin"]).strip():
                            st.session_state.update(rol="pareja", pareja_id=r["id"], intentos=0)
                            st.rerun()
                        else:
                            st.session_state.intentos = st.session_state.get("intentos", 0) + 1
                            st.error("PIN incorrecto.")
        with t2:
            with st.form("login_adm"):
                clave_ = st.text_input("Contraseña de administrador", type="password")
                if st.form_submit_button("Ingresar", type="primary", width="stretch"):
                    if verificar_admin(clave_):
                        st.session_state.update(rol="admin", intentos=0)
                        st.rerun()
                    else:
                        st.session_state.intentos = st.session_state.get("intentos", 0) + 1
                        st.error("Contraseña incorrecta.")
        modo = motor()[1]
        st.caption("🟢 Datos guardados en la nube" if modo == "nube" else "💾 Datos guardados en este computador (modo local)")


def barra(rol: str, nombre: str):
    sb = st.sidebar
    sb.markdown(logo_html(), unsafe_allow_html=True)
    sb.markdown(f"**Sesión:** {'🔐 Administrador' if rol == 'admin' else '👥 ' + nombre}")
    sb.caption(f"🕒 {ahora():%d/%m/%Y %H:%M}  ·  " + ("🟢 nube" if motor()[1] == "nube" else "💾 local"))
    if sb.button("🔄 Actualizar datos", width="stretch"):
        limpiar_caches_conteo()
        st.rerun()
    if sb.button("🚪 Cerrar sesión", width="stretch"):
        for k in ("rol", "pareja_id"):
            st.session_state.pop(k, None)
        st.rerun()


def main():
    st.markdown(CSS + CSS_EXTRA, unsafe_allow_html=True)
    try:
        motor()
    except Exception as e:
        st.error(f"No fue posible conectar con la base de datos: {e}")
        st.stop()
    rol = st.session_state.get("rol")
    if not rol:
        pantalla_login()
        return
    if rol == "pareja":
        P = leer_parejas()
        fila = P[P["id"] == st.session_state.get("pareja_id")]
        if fila.empty or fila.iloc[0]["estado"] != "Activa":
            st.session_state.pop("rol", None)
            st.warning("Su pareja fue finalizada o eliminada. Ingrese de nuevo.")
            st.rerun()
        par = fila.iloc[0].to_dict()
        barra("pareja", par["nombre"])
        ctx = contexto()
        st.markdown(f'<div class="banner"><h1>📡 Conteo · {par["nombre"]}</h1><p>Pistolee o digite. '
                    'Los registros se guardan al instante.</p></div>', unsafe_allow_html=True)
        pantalla_conteo(par, ctx)
        return
    # ---- Administrador
    barra("admin", "")
    ctx = contexto()
    st.markdown(f'<div class="banner"><h1>📦 Control de Inventario Físico · Smith & Nephew</h1>'
                f'<p>Tecnitrauma · Panel del administrador · {ahora():%d/%m/%Y %H:%M}</p></div>', unsafe_allow_html=True)
    if ctx["U"].empty:
        alerta("👉 Empiece en <b>⚙️ Maestros y configuración</b>: cargue NAL, Valref, Templete y TPN; luego cree las parejas.", "ambar")
    secciones = ["📊 Dashboard", "🏭 Smith & Nephew", "🌊 Serena del Mar", "🧰 Seriales", "👥 Parejas y trazabilidad",
                 "📡 Pistolear", "⚙️ Maestros y configuración"]
    sec = st.segmented_control("Sección", secciones, default=secciones[0], key="nav_admin",
                               label_visibility="collapsed") or secciones[0]
    st.write("")
    if sec == secciones[0]:
        admin_dashboard(ctx)
    elif sec == secciones[1]:
        admin_grupo(ctx, "SMITH")
    elif sec == secciones[2]:
        admin_grupo(ctx, "SERENA")
    elif sec == secciones[3]:
        admin_seriales(ctx)
    elif sec == secciones[4]:
        admin_parejas(ctx)
    elif sec == secciones[5]:
        P = leer_parejas()
        opciones = ["Administrador"] + (list(P["nombre"]) if not P.empty else [])
        quien = st.selectbox("Registrar a nombre de", opciones, key="adm_quien")
        if quien == "Administrador":
            par = dict(nombre="Administrador", aux1="", aux2="", zona=list(ZONAS)[0], gondolas="")
        else:
            par = P[P["nombre"] == quien].iloc[0].to_dict()
        pantalla_conteo(par, ctx, es_admin=True)
    else:
        admin_maestros(ctx)


if __name__ == "__main__":
    main()
