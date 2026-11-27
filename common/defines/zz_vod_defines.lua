-- Verge of Domination define overrides (vanilla values in common/defines/00_defines.lua)

-- Vanilla ends the game on 1949.1.1, before the 1950 bookmark starts.
NDefines.NGame.END_DATE = "1960.1.1.1"

-- World tension effects are scaled down month by month from 1936; start the scaling at the 1945 bookmark instead.
NDefines.NDiplomacy.TENSION_TIME_SCALE_START_DATE = "1945.1.1.12"
