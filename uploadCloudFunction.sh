echo "Deprecated: quickstartFunctions is legacy. Current backend is cloudrun/wantuju-api."
echo "Use cloudrun/wantuju-api deployment unless you are intentionally rolling back."
${installPath} cloud functions deploy --e ${envId} --n quickstartFunctions --r --project ${projectPath}
